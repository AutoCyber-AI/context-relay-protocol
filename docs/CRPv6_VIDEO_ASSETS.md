# CRPv6 Video Assets — Complete Inventory

> Every artifact you need to produce a CRP-vs-raw-LLM product video, pitch deck, or recorded demo.

---

## 1. The single "one thing to show" asset

| Path | What it is | How to use it |
|---|---|---|
| `examples/crp_demos/video_kit.py` | Script that generates a self-contained HTML slide deck from the live demo. | Run `python examples/crp_demos/video_kit.py`. It refreshes the live artifact and produces `_video_kit.html`. |
| `examples/crp_demos/_video_kit.html` | **Single-file browser presentation** with raw-vs-CRP, chain-of-thought, governance cards, and CTA. | Open in browser, scroll through slides, screen-record. |
| `examples/crp_demos/_video_kit_script.md` | Presenter narration script matching the HTML slides. | Read as voiceover or teleprompter text. |

---

## 2. Live demo runner and artifacts

| Path | What it is | How to use it |
|---|---|---|
| `examples/crp_demos/unified_video_demo.py` | Runs the same question through raw LLM, CRP agent (no preset), and CRP agent (`research_assistant` preset). | `python examples/crp_demos/unified_video_demo.py` |
| `examples/crp_demos/_unified_demo.json` | Structured side-by-side proof artifact from the latest live run. | Source data for the video kit or custom editing. |
| `examples/crp_demos/_unified_demo.md` | Readable Markdown report generated from the JSON artifact. | Drop into a deck or paste into documentation. |

---

## 3. Narrative and explanation docs

| Path | What it is | Best for |
|---|---|---|
| `docs/CRPv6_VIDEO_STORYBOARD.md` | 120-second shot list with voiceover and captions. | Planning an edited video. |
| `docs/CRPv6_LIVE_PROOF_SUMMARY.md` | Honest results from LM Studio and hosted-model SQB runs. | Evidence slide / investor appendix. |
| `docs/CRPv6_COMPANY_ANNOUNCEMENT.md` | Press/investor announcement draft. | Website copy, press release, pitch intro. |
| `docs/CRPv6_AGENTIC_ECOSYSTEM_CAPABILITIES.md` | Every user-configurable surface. | Deep-dive on what users can set and trust. |
| `docs/CRPv6_TOOLS_AND_MCP.md` | How tools connect, with and without MCP. | Answering "is this MCP?" / integration FAQ. |
| `docs/CRP_AGENT_CONSOLE_DEPLOYMENT_GUIDE.md` | How to build and host the console via npm/Vite/CDN. | Console infrastructure slide. |

---

## 4. Supporting demo scripts

| Path | What it is | Best for |
|---|---|---|
| `examples/templates/robot_safeguard_agent.py` | Robot-with-safeguard preset demo. | "Values as runtime rules" moment in the video. |
| `examples/agents/weather_agent.py` | Original weather agent template. | Earlier SDK example. |
| `examples/agents/rag_agent.py` | RAG agent with CKF carry-forward. | Showing knowledge/memory use. |
| `examples/agents/report_agent.py` | Scan → summarize → report pipeline. | Showing multi-operation workflows. |

---

## 5. Visual / brand assets

| Path | What it is | Best for |
|---|---|---|
| `media/FINAL_CRP_Full_logo-transparent.png` | CRP logo with transparent background. | End slide, watermark, pitch deck cover. |
| `site-docs/assets/logo-full-readme.png` | Logo optimized for README/site. | Web embeds. |

---

## 6. Benchmark / proof artifacts

| Path | What it is | Best for |
|---|---|---|
| `sqb_results/sqb_hosted_20260829T113111Z.json` | Full hosted-model SQB run proving all five gate criteria pass. | "We proved it" slide. |
| `sqb_results/quality_benchmark.json` | Prior hosted-model quality benchmark (8.31/10). | Quality score slide. |

---

## 7. Suggested 2-minute video structure using these assets

1. **Hook** — open `_video_kit.html` slide 1, logo + tagline.
2. **The question** — slide 2.
3. **The failure** — slide 3 left side (raw LLM emits JSON but executes nothing).
4. **The CRP difference** — slide 3 right side (live weather + governance cards).
5. **Chain of thought** — slide 4, walk the timeline.
6. **Presets** — slide 5, show the same answer under a reasoning preset.
7. **Why CRPv6** — slide 6, six differentiator cards.
8. **CTA** — slide 7, install command + PyPI link.

Voiceover: use `_video_kit_script.md`.

---

## 8. How to refresh everything before recording

```bash
# 1. Make sure LM Studio is running with a loaded model.
# 2. Refresh the live artifact and video kit:
python examples/crp_demos/video_kit.py

# 3. Open the kit:
start examples/crp_demos/_video_kit.html   # Windows
open examples/crp_demos/_video_kit.html   # macOS
xdg-open examples/crp_demos/_video_kit.html # Linux
```

All outputs are local, reproducible, and driven by the real loaded model.
