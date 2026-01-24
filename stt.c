#include "stt.h"

#include <curl/curl.h>
#include <portaudio.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>

#define SAMPLE_RATE 16000
#define CHANNELS 1
#define FRAMES_PER_BUFFER 480
#define MAX_SECONDS 30
#define MAX_FRAMES (SAMPLE_RATE * MAX_SECONDS)

static short *recorded_samples = NULL;
static int frame_index = 0;
static PaStream *stream = NULL;
static bool recording = false;
static bool initialized = false;

#define STT_LOG(fmt, ...) fprintf(stderr, "[stt] " fmt "\n", ##__VA_ARGS__)

struct string_buffer
{
    char *data;
    size_t length;
    size_t capacity;
};

static void sb_init(struct string_buffer *buf)
{
    buf->data = NULL;
    buf->length = 0;
    buf->capacity = 0;
}

static void sb_append(struct string_buffer *buf, const char *src, size_t src_len)
{
    if (src_len == 0)
    {
        return;
    }
    if (buf->length + src_len + 1 > buf->capacity)
    {
        size_t new_capacity = buf->capacity == 0 ? src_len + 128 : buf->capacity * 2;
        while (new_capacity < buf->length + src_len + 1)
        {
            new_capacity *= 2;
        }
        char *new_data = realloc(buf->data, new_capacity);
        if (!new_data)
        {
            STT_LOG("buffer realloc failed (requested=%zu)", new_capacity);
            return;
        }
        buf->data = new_data;
        buf->capacity = new_capacity;
    }
    memcpy(buf->data + buf->length, src, src_len);
    buf->length += src_len;
    buf->data[buf->length] = '\0';
}

static void sb_free(struct string_buffer *buf)
{
    free(buf->data);
    buf->data = NULL;
    buf->length = 0;
    buf->capacity = 0;
}

static size_t response_write(void *contents, size_t size, size_t nmemb, void *userp)
{
    struct string_buffer *buf = (struct string_buffer *)userp;
    size_t total = size * nmemb;
    sb_append(buf, (const char *)contents, total);
    return total;
}

static int audio_callback(const void *input, void *output, unsigned long frameCount,
                          const PaStreamCallbackTimeInfo *timeInfo,
                          PaStreamCallbackFlags statusFlags, void *userData)
{
    (void)output;
    (void)timeInfo;
    (void)statusFlags;
    (void)userData;

    if (!recording || !input)
    {
        return paContinue;
    }

    int remaining_frames = MAX_FRAMES - frame_index;
    if (remaining_frames <= 0)
    {
        return paComplete;
    }

    unsigned long frames_to_copy = frameCount;
    if ((int)frames_to_copy > remaining_frames)
    {
        frames_to_copy = remaining_frames;
    }

    memcpy(recorded_samples + frame_index, input, frames_to_copy * sizeof(short));
    frame_index += frames_to_copy;

    return frame_index >= MAX_FRAMES ? paComplete : paContinue;
}

static bool ensure_initialized(void)
{
    if (initialized)
    {
        return true;
    }

    PaError pa_init = Pa_Initialize();
    if (pa_init != paNoError)
    {
        STT_LOG("Pa_Initialize failed: %s", Pa_GetErrorText(pa_init));
        return false;
    }

    curl_global_init(CURL_GLOBAL_DEFAULT);

    recorded_samples = calloc(MAX_FRAMES, sizeof(short));
    if (!recorded_samples)
    {
        STT_LOG("recorded_samples allocation failed");
        curl_global_cleanup();
        Pa_Terminate();
        return false;
    }

    initialized = true;
    STT_LOG("initialized (sample_rate=%d, max_frames=%d)", SAMPLE_RATE, MAX_FRAMES);
    return true;
}

static void cleanup_stream(void)
{
    if (stream)
    {
        Pa_AbortStream(stream);
        Pa_CloseStream(stream);
        stream = NULL;
    }
}

static char *create_temp_wav_path(void)
{
    // Create a temp file that already ends with .wav so downstream tools infer type cleanly
    char template[] = "/tmp/xiaozhi_stt_XXXXXX.wav";
#ifdef __GLIBC__
    int fd = mkstemps(template, 4); // 4 chars suffix: ".wav"
#else
    // Fallback: create no-suffix file, then append .wav by renaming
    char nosuf[] = "/tmp/xiaozhi_stt_XXXXXX";
    int fd = mkstemp(nosuf);
    if (fd >= 0)
    {
        char *with_suffix = NULL;
        if (asprintf(&with_suffix, "%s.wav", nosuf) == -1)
        {
            close(fd);
            unlink(nosuf);
            STT_LOG("asprintf failed for temp wav path");
            return NULL;
        }
        if (rename(nosuf, with_suffix) != 0)
        {
            int e = errno;
            close(fd);
            unlink(nosuf);
            free(with_suffix);
            STT_LOG("rename temp file failed: %s", strerror(e));
            return NULL;
        }
        strncpy(template, with_suffix, sizeof(template) - 1);
        template[sizeof(template) - 1] = '\0';
        free(with_suffix);
    }
#endif
    if (fd < 0)
    {
        STT_LOG("mkstemp(s) failed for temp wav file");
        return NULL;
    }
    close(fd);
    return strdup(template);
}

static bool write_wav_file(const char *filename, short *data, int samples)
{
    FILE *f = fopen(filename, "wb");
    if (!f)
    {
        STT_LOG("failed to open wav file for writing: %s", filename);
        return false;
    }

    int byte_rate = SAMPLE_RATE * CHANNELS * 2;
    int block_align = CHANNELS * 2;
    int data_size = samples * 2;

    fwrite("RIFF", 1, 4, f);
    int chunk_size = 36 + data_size;
    fwrite(&chunk_size, 4, 1, f);
    fwrite("WAVEfmt ", 1, 8, f);

    int subchunk1 = 16;
    short audio_format = 1;
    fwrite(&subchunk1, 4, 1, f);
    fwrite(&audio_format, 2, 1, f);
    fwrite(&(short){CHANNELS}, 2, 1, f);
    fwrite(&(int){SAMPLE_RATE}, 4, 1, f);
    fwrite(&byte_rate, 4, 1, f);
    fwrite(&block_align, 2, 1, f);
    fwrite(&(short){16}, 2, 1, f);

    fwrite("data", 1, 4, f);
    fwrite(&data_size, 4, 1, f);
    fwrite(data, 2, samples, f);

    fclose(f);
    return true;
}

static char *extract_text_field(const char *json)
{
    if (!json)
        return NULL;

    const char *key = "\"text\"";
    const char *p = strstr(json, key);
    if (!p)
        return NULL;
    p += strlen(key);
    // skip whitespace and colon
    while (*p && (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r'))
        ++p;
    if (*p != ':')
        return NULL;
    ++p;
    while (*p && (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r'))
        ++p;
    if (*p != '"')
        return NULL;
    ++p; // inside the string

    // Extract until unescaped quote
    struct string_buffer out;
    sb_init(&out);
    for (; *p; ++p)
    {
        if (*p == '"')
        {
            // end of string
            break;
        }
        if (*p == '\\')
        {
            ++p;
            if (!*p)
                break;
            char c = *p;
            switch (c)
            {
            case 'n':
                sb_append(&out, "\n", 1);
                break;
            case 'r':
                sb_append(&out, "\r", 1);
                break;
            case 't':
                sb_append(&out, "\t", 1);
                break;
            case '"':
                sb_append(&out, "\"", 1);
                break;
            case '\\':
                sb_append(&out, "\\", 1);
                break;
            default:
                // For unknown escapes, keep the character as-is
                sb_append(&out, &c, 1);
                break;
            }
        }
        else
        {
            sb_append(&out, p, 1);
        }
    }

    char *result = NULL;
    if (out.length > 0)
        result = strdup(out.data);
    sb_free(&out);
    return result;
}

static char *transcribe_from_file(const char *filepath)
{
    if (!filepath)
    {
        STT_LOG("transcribe_from_file called with null path");
        return NULL;
    }

    const char *api_key = getenv("GROQ_API_KEY");
    if (!api_key || api_key[0] == '\0')
    {
        STT_LOG("GROQ_API_KEY is not set");
        return NULL;
    }

    struct string_buffer response;
    sb_init(&response);

    CURL *curl = curl_easy_init();
    if (!curl)
    {
        STT_LOG("curl_easy_init failed");
        sb_free(&response);
        return NULL;
    }

    struct curl_slist *headers = NULL;
    char auth_header[256];
    snprintf(auth_header, sizeof(auth_header), "Authorization: Bearer %s", api_key);
    headers = curl_slist_append(headers, auth_header);
    headers = curl_slist_append(headers, "Accept: application/json");

    curl_easy_setopt(curl, CURLOPT_URL, "https://api.groq.com/openai/v1/audio/transcriptions");
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, response_write);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
    // Do not fail on HTTP error so we can capture and log body
    curl_easy_setopt(curl, CURLOPT_FAILONERROR, 0L);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 60L);

    char errbuf[CURL_ERROR_SIZE] = {0};
    curl_easy_setopt(curl, CURLOPT_ERRORBUFFER, errbuf);

    curl_mime *mime = curl_mime_init(curl);
    curl_mimepart *part = curl_mime_addpart(mime);
    curl_mime_name(part, "file");
    curl_mime_filedata(part, filepath);
    curl_mime_type(part, "audio/wav");
    curl_mime_filename(part, "audio.wav");

    part = curl_mime_addpart(mime);
    curl_mime_name(part, "model");
    curl_mime_data(part, "whisper-large-v3-turbo", CURL_ZERO_TERMINATED);

    // Optional: set language if provided (ISO-639-1), improves accuracy/latency
    const char *lang = getenv("STT_LANGUAGE");
    if (lang && *lang)
    {
        part = curl_mime_addpart(mime);
        curl_mime_name(part, "language");
        curl_mime_data(part, lang, CURL_ZERO_TERMINATED);
    }

    // Request JSON response and extract the text field below
    part = curl_mime_addpart(mime);
    curl_mime_name(part, "response_format");
    curl_mime_data(part, "json", CURL_ZERO_TERMINATED);

    curl_easy_setopt(curl, CURLOPT_MIMEPOST, mime);

    STT_LOG("sending audio to Groq: %s", filepath);
    CURLcode code = curl_easy_perform(curl);

    char *result = NULL;
    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    if (code != CURLE_OK)
    {
        if (errbuf[0])
            STT_LOG("curl error: %s", errbuf);
        else
            STT_LOG("curl error: %s", curl_easy_strerror(code));
        if (response.length > 0)
            STT_LOG("response body: %.*s", (int)response.length, response.data);
    }
    else if (http_code >= 400)
    {
        STT_LOG("http error %ld, body: %.*s", http_code, (int)response.length, response.data);
    }
    else if (response.length > 0)
    {
        STT_LOG("transcription response received (%zu bytes)", response.length);
        // Try to extract just the text, else return full body
        char *only_text = extract_text_field(response.data);
        result = only_text ? only_text : strdup(response.data);
    }
    else
    {
        STT_LOG("empty transcription response");
    }

    curl_mime_free(mime);
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    sb_free(&response);

    return result;
}

int stt_initialize(void)
{
    STT_LOG("stt_initialize called");
    return ensure_initialized() ? 0 : -1;
}

int stt_start_recording(void)
{
    STT_LOG("stt_start_recording called");
    if (!ensure_initialized())
    {
        STT_LOG("start_recording failed: not initialized");
        return -1;
    }
    if (recording)
    {
        STT_LOG("start_recording ignored: already recording");
        return -1;
    }

    frame_index = 0;
    memset(recorded_samples, 0, MAX_FRAMES * sizeof(short));

    PaError err = Pa_OpenDefaultStream(&stream, 1, 0, paInt16, SAMPLE_RATE, FRAMES_PER_BUFFER,
                                       audio_callback, NULL);
    if (err != paNoError)
    {
        STT_LOG("Pa_OpenDefaultStream failed: %s", Pa_GetErrorText(err));
        stream = NULL;
        return -1;
    }

    err = Pa_StartStream(stream);
    if (err != paNoError)
    {
        STT_LOG("Pa_StartStream failed: %s", Pa_GetErrorText(err));
        Pa_CloseStream(stream);
        stream = NULL;
        return -1;
    }

    recording = true;
    STT_LOG("recording started");
    return 0;
}

char *stt_stop_recording_and_transcribe(void)
{
    STT_LOG("stt_stop_recording_and_transcribe called");
    if (!recording)
    {
        STT_LOG("stop_recording ignored: not recording");
        return NULL;
    }

    recording = false;

    if (stream)
    {
        Pa_StopStream(stream);
        Pa_CloseStream(stream);
        stream = NULL;
    }

    if (frame_index <= 0)
    {
        STT_LOG("no audio captured, frame_index=%d", frame_index);
        return NULL;
    }

    char *tmp_path = create_temp_wav_path();
    if (!tmp_path)
    {
        STT_LOG("failed to create temp wav path");
        return NULL;
    }

    bool wrote = write_wav_file(tmp_path, recorded_samples, frame_index);
    if (!wrote)
    {
        STT_LOG("failed to write wav file");
        unlink(tmp_path);
        free(tmp_path);
        return NULL;
    }

    STT_LOG("wav file written: %s (frames=%d)", tmp_path, frame_index);

    char *transcription = transcribe_from_file(tmp_path);
    unlink(tmp_path);
    free(tmp_path);

    if (!transcription)
    {
        STT_LOG("transcription failed or empty");
    }

    return transcription;
}

void stt_free_transcription(char *value)
{
    free(value);
}

int stt_is_recording(void)
{
    return recording ? 1 : 0;
}

void stt_shutdown(void)
{
    if (!initialized)
    {
        return;
    }

    recording = false;
    cleanup_stream();
    curl_global_cleanup();
    Pa_Terminate();
    free(recorded_samples);
    recorded_samples = NULL;
    initialized = false;
    STT_LOG("shutdown complete");
}
