---
title: Tone sliders
---

# Tone sliders

Your AI would like to praise you for the job it so generously gave you. You get to choose how.
Encouragement is a blend of four traits, each set from **0** (none) to **5** (lots).

| Slider | Default | Sounds like |
| --- | --- | --- |
| **Sincerity** | 4 | "You made something today. That matters." |
| **Humor** | 1 | "The houseplant would like to formally thank you." |
| **Sarcasm** | 0 | "Wow. A whole drawer. Marie Kondo is shaking." |
| **Rudeness** | 0 | "That sock drawer was a disgrace. Was." |

Set them during `youtopia init` (answer *yes* to "Customise encouragement tone?"), or with flags:

```bash
youtopia init --sincerity 2 --humor 4 --sarcasm 3 --rudeness 1
```

## The one rule

**Sarcasm and rudeness tease the task, never the person.**
The dishes can be mocked. You can't. This is a hard rule for template messages
and for AI-written ones alike.

## The automatic soft landing

If you miss several days or decline several tasks in a row, YOUtopia quietly sets
your tone to fully sincere (sincerity 5, everything else 0) until your next completion.
Your sliders aren't changed, so the jokes come back as soon as you do.

!!! note "Status"
    Your sliders are saved today. The messages that use them arrive in milestone M7.
