# Deep Research Agent

Baseline loop:

```text
question → Deep Agent → search tool → answer
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Edit `.env` and paste your keys. Recommended default is **Gemini** (already first-class in Deep Agents, simple free-tier setup):

```env
TAVILY_API_KEY=tvly-...
GOOGLE_API_KEY=...
MODEL=google_genai:gemini-2.5-flash
```

Alternatives in the same file:

| Provider   | Env var             | Example `MODEL`                         |
|------------|---------------------|-----------------------------------------|
| Gemini     | `GOOGLE_API_KEY`    | `google_genai:gemini-2.5-flash`         |
| OpenRouter | `OPENROUTER_API_KEY`| `openrouter:google/gemini-2.5-flash`    |
| Groq       | `GROQ_API_KEY`      | `groq:llama-3.3-70b-versatile`          |

Only one LLM provider key is required (plus Tavily).

## Run

```bash
python -m src.agent \
  "What are the major approaches to evaluating coding agents?"
```

Override the model for a single run:

```bash
python -m src.agent --model "openrouter:google/gemini-2.5-flash" "Your question"
```
