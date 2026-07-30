# Gate 2-A runtime usage policy

- User-local venv only; system-wide installation is forbidden.
- Only exact Wave 1 wheels from the recorded wheelhouse may be installed.
- Source builds, package substitution, Docker, WSL, GPU/CUDA changes, and base-runtime mutation are forbidden.
- Synthetic smoke tests may run; real race data, targets, metrics, training, final-lock unlock and automation activation are forbidden.
- Any package upgrade creates a new runtime manifest; the old runtime is retained.
