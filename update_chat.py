import re

path = /home/meritech/Manas_research/Vaultcity.ai/frontend/src/components/ChatView.tsx
with open(path, r, encoding=utf-8) as f:
    content = f.read()

# 1. Update container breakpoints
content = content.replace(
    sm:h-[calc(100vh-160px)]
