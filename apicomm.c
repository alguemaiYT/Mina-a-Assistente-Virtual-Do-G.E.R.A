#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <curl/curl.h>
#include <cjson/cJSON.h>
#include <time.h>

#define USER_INPUT_SIZE 1024 // renamed from MAX_INPUT to avoid conflict
#define END_SENTINEL "<<END>>\n"
#define MAX_EMOTION_LINE 256
#define CURL_TIMEOUT_MS 30000L
#define CURL_CONNECT_TIMEOUT_MS 8000L
#define CURL_LOW_SPEED_LIMIT 10L
#define CURL_LOW_SPEED_TIME 10L

struct buffer
{
    char *data;
    size_t len;
    char *emotion_buf;
    size_t emotion_len;
    int emotion_done;
};

// Minimal JSON string escaper for content field
static void json_escape(const char *src, char *dst, size_t cap)
{
    size_t j = 0;
    for (size_t i = 0; src[i] && j + 2 < cap; ++i)
    {
        char c = src[i];
        switch (c)
        {
        case '\\':
            dst[j++] = '\\';
            dst[j++] = '\\';
            break;
        case '"':
            dst[j++] = '\\';
            dst[j++] = '"';
            break;
        case '\n':
            dst[j++] = '\\';
            dst[j++] = 'n';
            break;
        case '\r':
            dst[j++] = '\\';
            dst[j++] = 'r';
            break;
        case '\t':
            dst[j++] = '\\';
            dst[j++] = 't';
            break;
        default:
            dst[j++] = c;
        }
    }
    dst[j] = '\0';
}

// Callback for streaming chunks; keeps partial lines intact between calls
size_t stream_cb(char *ptr, size_t size, size_t nmemb, void *userdata)
{
    struct buffer *buf = (struct buffer *)userdata;
    size_t chunk_size = size * nmemb;
    size_t new_len = buf->len + chunk_size;
    char *new_data = realloc(buf->data, new_len + 1);
    if (!new_data)
    {
        return 0; // abort on OOM
    }
    buf->data = new_data;
    memcpy(buf->data + buf->len, ptr, chunk_size);
    buf->len = new_len;
    buf->data[buf->len] = '\0';

    size_t processed = 0;
    while (processed < buf->len)
    {
        char *newline = memchr(buf->data + processed, '\n', buf->len - processed);
        if (!newline)
        {
            break; // keep partial line for next chunk
        }

        size_t line_len = (size_t)(newline - (buf->data + processed));
        char saved = buf->data[processed + line_len];
        buf->data[processed + line_len] = '\0';

        char *line = buf->data + processed;
        if (strncmp(line, "data: ", 6) == 0 && strcmp(line + 6, "[DONE]") != 0)
        {
            cJSON *obj = cJSON_Parse(line + 6);
            if (obj)
            {
                cJSON *choices = cJSON_GetObjectItem(obj, "choices");
                if (cJSON_IsArray(choices) && cJSON_GetArraySize(choices) > 0)
                {
                    cJSON *delta = cJSON_GetObjectItem(cJSON_GetArrayItem(choices, 0), "delta");
                    if (delta)
                    {
                        cJSON *content = cJSON_GetObjectItem(delta, "content");
                        if (cJSON_IsString(content))
                        {
                            const char *text = content->valuestring;

                            // If we haven't resolved emotion yet, accumulate until newline
                            if (!buf->emotion_done)
                            {
                                size_t text_len = strlen(text);
                                size_t new_len = buf->emotion_len + text_len;
                                if (new_len > MAX_EMOTION_LINE)
                                {
                                    // too long without newline; treat as normal text
                                    if (buf->emotion_buf && buf->emotion_len)
                                    {
                                        printf("%s", buf->emotion_buf);
                                        fflush(stdout);
                                    }
                                    buf->emotion_done = 1;
                                    buf->emotion_len = 0;
                                    free(buf->emotion_buf);
                                    buf->emotion_buf = NULL;
                                    printf("%s", text);
                                    fflush(stdout);
                                }
                                else
                                {
                                    char *new_emotion = realloc(buf->emotion_buf, new_len + 1);
                                    if (!new_emotion)
                                    {
                                        return 0;
                                    }
                                    buf->emotion_buf = new_emotion;
                                    memcpy(buf->emotion_buf + buf->emotion_len, text, text_len);
                                    buf->emotion_len = new_len;
                                    buf->emotion_buf[buf->emotion_len] = '\0';
                                }

                                char *nl = strchr(buf->emotion_buf, '\n');
                                if (nl)
                                {
                                    *nl = '\0';
                                    if (strncmp(buf->emotion_buf, "EMOTION:", 8) == 0)
                                    {
                                        const char *emo = buf->emotion_buf + 8;
                                        while (*emo == ' ')
                                            emo++;
                                        if (*emo)
                                        {
                                            printf("EMOTION:%s\n", emo);
                                            fflush(stdout);
                                        }
                                        // print remaining after newline (if any)
                                        const char *rest = nl + 1;
                                        if (*rest)
                                        {
                                            printf("%s", rest);
                                            fflush(stdout);
                                        }
                                    }
                                    else
                                    {
                                        // No emotion line; print what we have as text
                                        printf("%s\n", buf->emotion_buf);
                                        fflush(stdout);
                                    }

                                    buf->emotion_done = 1;
                                    buf->emotion_len = 0;
                                    free(buf->emotion_buf);
                                    buf->emotion_buf = NULL;
                                }
                            }
                            else
                            {
                                printf("%s", text);
                                fflush(stdout);
                            }
                        }
                    }
                }
                cJSON_Delete(obj);
            }
        }

        buf->data[processed + line_len] = saved;
        processed += line_len + 1; // move past the newline
    }

    // Preserve any partial line by shifting it to the start
    if (processed < buf->len)
    {
        size_t remaining = buf->len - processed;
        memmove(buf->data, buf->data + processed, remaining);
        buf->len = remaining;
    }
    else
    {
        buf->len = 0;
    }

    return chunk_size;
}

int main()
{
    CURL *curl;
    CURLcode res;
    struct curl_slist *headers = NULL;
    struct buffer buf = {NULL, 0, NULL, 0, 0};

    const char *api_key = getenv("GROQ_API_KEY");
    if (!api_key)
    {
        fprintf(stderr, "Set GROQ_API_KEY environment variable!\n");
        return 1;
    }

    curl_global_init(CURL_GLOBAL_DEFAULT);
    curl = curl_easy_init();
    if (!curl)
        return 1;

    headers = curl_slist_append(headers, "Content-Type: application/json");
    char auth[256];
    snprintf(auth, sizeof(auth), "Authorization: Bearer %s", api_key);
    headers = curl_slist_append(headers, auth);

    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, stream_cb);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &buf);
    curl_easy_setopt(curl, CURLOPT_TCP_NODELAY, 1L);
    curl_easy_setopt(curl, CURLOPT_NOSIGNAL, 1L);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT_MS, CURL_CONNECT_TIMEOUT_MS);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, CURL_TIMEOUT_MS);
    curl_easy_setopt(curl, CURLOPT_LOW_SPEED_LIMIT, CURL_LOW_SPEED_LIMIT);
    curl_easy_setopt(curl, CURLOPT_LOW_SPEED_TIME, CURL_LOW_SPEED_TIME);

    char input[USER_INPUT_SIZE];

    while (1)
    {
        if (!fgets(input, USER_INPUT_SIZE, stdin))
        {
            break;
        }

        // Remove newline
        input[strcspn(input, "\n")] = 0;
        if (strlen(input) == 0)
        {
            continue;
        }

        char escaped[USER_INPUT_SIZE * 2];
        json_escape(input, escaped, sizeof(escaped));

        char json_body[8192];
        snprintf(json_body, sizeof(json_body),
                 "{"
                 "\"model\":\"openai/gpt-oss-20b\"," // adjust via env if needed
                 "\"stream\":true,"
                 "\"temperature\":0.2,"
                 "\"top_p\":0.9,"
                 "\"max_tokens\":256,"
                 "\"presence_penalty\":0,"
                 "\"frequency_penalty\":0,"
                 "\"messages\":["
                 "{\"role\":\"system\",\"content\":\"Você é o Xiaozhi AI. Responda em português. Primeira linha obrigatória: EMOTION:<nome>. Escolha exatamente um dentre: angry, confident, confused, cool, crying, delicious, embarrassed, funny, happy, kissy, laughing, loving, neutral, relaxed, sad, shocked, silly, sleepy, surprised, thinking, winking. Após a primeira linha, escreva apenas a resposta ao usuário sem repetir o rótulo EMOTION. Seja conciso.\"},"
                 "{\"role\":\"user\",\"content\":\"%s\"}"
                 "]"
                 "}",
                 escaped);

        clock_t start = clock();
        curl_easy_setopt(curl, CURLOPT_URL, "https://api.groq.com/openai/v1/chat/completions");
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, json_body);

        buf.len = 0;
        free(buf.data);
        buf.data = NULL;
        buf.emotion_done = 0;
        buf.emotion_len = 0;
        free(buf.emotion_buf);
        buf.emotion_buf = NULL;

        res = curl_easy_perform(curl);
        if (res != CURLE_OK)
        {
            fprintf(stderr, "Request failed: %s\n", curl_easy_strerror(res));
        }
        clock_t end = clock();
        double latency = (double)(end - start) / CLOCKS_PER_SEC;
        fprintf(stderr, "[Latency: %.3f sec]\n", latency);

        // Mark end of response for upstream consumers
        printf("\n%s", END_SENTINEL);
        fflush(stdout);
    }

    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    curl_global_cleanup();
    free(buf.data);
    free(buf.emotion_buf);

    return 0;
}
