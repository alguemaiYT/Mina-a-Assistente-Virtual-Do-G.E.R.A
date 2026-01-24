#ifndef STT_H
#define STT_H

#ifdef __cplusplus
extern "C"
{
#endif

    int stt_initialize(void);
    int stt_start_recording(void);
    char *stt_stop_recording_and_transcribe(void);
    void stt_free_transcription(char *value);
    int stt_is_recording(void);
    void stt_shutdown(void);

#ifdef __cplusplus
}
#endif

#endif // STT_H
