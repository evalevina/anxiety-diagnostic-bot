# Private product materials

Paid content is not distributed in this repository. Supply the files privately on the server before enabling sales:

| Profile | PDF | Audio files |
| --- | --- | --- |
| A — Scanner | `razbor_A.pdf` | `audio_A1.mp3`, `audio_A2.mp3`, `audio_A3.mp3` |
| B — Catastrophist | `razbor_B.pdf` | `audio_B1.mp3`, `audio_B2.mp3`, `audio_B3.mp3` |
| C — Freezer | `razbor_C.pdf` | `audio_C1.mp3`, `audio_C2.mp3`, `audio_C3.mp3` |
| D — Controller | `razbor_D.pdf` | `audio_D1.mp3`, `audio_D2.mp3`, `audio_D3.mp3` |

The shared bonus video is `webinar.mp4`. Optional per-profile PDF URLs in `.env` take precedence over local PDFs. The generic `razbor.pdf` is not used by `send_materials`.

Do not create zero-byte placeholders: the current delivery function silently skips missing or empty files. Check playback, file sizes supported by Telegram and the complete delivery flow before accepting payments. Keep a private backup and make sure the offer describes the actual delivered content.
