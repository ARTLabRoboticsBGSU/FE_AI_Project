#!/usr/bin/env python
import subprocess
import sys

# Read requirements
with open('requirements.txt') as f:
    all_reqs = [line.strip() for line in f if line.strip()]

# Packages that need compilation and don't have wheels for Python 3.14
skip_packages = {
    'contourpy', 'numpy', 'fonttools', 'matplotlib', 'lxml',
    'scipy', 'scikit-learn', 'torch', 'transformers', 'sentence-transformers',
    'nvidia-cuda-cupti-cu12', 'nvidia-cuda-nvrtc-cu12', 'nvidia-cuda-runtime-cu12',
    'nvidia-cudnn-cu12', 'nvidia-cufft-cu12', 'nvidia-cufile-cu12',
    'nvidia-cusparse-cu12', 'nvidia-cusparselt-cu12', 'nvidia-nccl-cu12',
    'nvidia-nvjitlink-cu12', 'nvidia-nvshmem-cu12', 'triton', 'uvloop'
}

# Filter requirements
filtered_reqs = [req for req in all_reqs if not any(pkg in req for pkg in skip_packages)]

print(f"Installing {len(filtered_reqs)} packages...")
print(f"Skipping {len(all_reqs) - len(filtered_reqs)} packages that require compilation:\n  {', '.join(skip_packages)}\n")

# Install
cmd = [sys.executable, '-m', 'pip', 'install', '--prefer-binary'] + filtered_reqs
result = subprocess.run(cmd)
sys.exit(result.returncode)
