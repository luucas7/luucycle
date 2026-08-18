# luucycle Roster

Single source of truth for available workers. You may update this file mid-process if you discover missing CLI arguments (e.g., via `--help`). Toggle `Accessible: true|false` instead of deleting models. Agent facts only — role → agent mapping lives in `ROLES.md`.

- **Agent**: Deepseek V4 Flash
  - **Command**: `cline`
  - **Model Flag**: 
  - **Bypass Flag**: 
  - **Accessible**: true
  - **Cost**: low
  - **Strengths**: Near-free and low on errors, at the cost of raw sharpness. Reliable for straightforward, repetitive tasks.

- **Agent**: Gemini Pro 3.1
  - **Command**: `agy`
  - **Model Flag**: `--model=gemini-3.1-pro-high`
  - **Bypass Flag**: `--dangerously-skip-permissions`
  - **Accessible**: true
  - **Cost**: low
  - **Strengths**: Reasonably bright for almost nothing, but effort ceiling is modest. Good pair of hands for light work.

- **Agent**: Sol
  - **Command**: `codex`
  - **Model Flag**: 
  - **Bypass Flag**: 
  - **Accessible**: false
  - **Cost**: high
  - **Strengths**: The sharpest in the roster. Unmatched for complex reasoning, architectural leaps, and deep refactoring.

- **Agent**: Luna
  - **Command**: `codex`
  - **Model Flag**: 
  - **Bypass Flag**: 
  - **Accessible**: false
  - **Cost**: medium
  - **Strengths**: The best value-for-money. High quality, sharp enough for most feature work without the extreme cost of Sol.

- **Agent**: freebuff
  - **Command**: `freebuff`
  - **Model Flag**: none — interactive picker only (default DeepSeek V4 Pro 08/13; falls back to DeepSeek V4 Flash 07/31 when premium sessions run out)
  - **Bypass Flag**: none — interactive TUI; permissions are handled in-session, no `--bypass-permissions`
  - **Accessible**: true
  - **Cost**: medium
  - **Strengths**: Dependable generalist. Steady on mid-complexity code and honest about its limits. Built on the Codebuff platform.

- **Agent**: GPT-5 mini
  - **Command**: `copilot`
  - **Model Flag**: none — auto default (the `--model` flag rejects every explicit ID on this plan, verified 2026-08-18)
  - **Bypass Flag**: `--allow-all`
  - **Accessible**: true
  - **Cost**: low
  - **Strengths**: Lightweight and cheap, but soft — fine for bulk passes, not for sharp reasoning. Keep it as the spare, not the plan.

- **Agent**: deepseek-flash
  - **Command**: `orca-cli`
  - **Model Flag**: `--model=opencode/deepseek-v4-flash-free`
  - **Bypass Flag**: `--bypass-permissions`
  - **Accessible**: true
  - **Cost**: low
  - **Strengths**: Extremely fast and practically free. Excellent for rapid scaffolding, generating boilerplate, and bulk text processing, but lacks deep reasoning for complex architecture.

- **Agent**: Kimi K3
  - **Command**: `orca-cli`
  - **Model Flag**: `--model=modal/moonshotai/Kimi-K3`
  - **Bypass Flag**: `--bypass-permissions`
  - **Accessible**: false
  - **Cost**: high
  - **Strengths**: Exceptional at handling massive contexts. Very, very good at absorbing entire codebases or huge documentation pages to synthesize precise answers.

- **Agent**: Claude Opus 4.6
  - **Command**: `agy`
  - **Model Flag**: `--model=claude-opus-4-6-thinking`
  - **Bypass Flag**: `--dangerously-skip-permissions`
  - **Accessible**: true
  - **Cost**: high
  - **Strengths**: Top-tier reasoning and architecture. The sharpest via agy — complex reasoning, deep debugging, high-stakes decisions.

- **Agent**: Gemini 3.7 Flash
  - **Command**: `agy`
  - **Model Flag**: `--model=gemini-3.7-flash-high`
  - **Bypass Flag**: `--dangerously-skip-permissions`
  - **Accessible**: true
  - **Cost**: low
  - **Strengths**: Cheap and fast, brighter than Gemini Pro 3.1 with a higher ceiling. Solid all-rounder for mid-complexity work.
