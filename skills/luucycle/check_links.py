import os
import re

skill_dir = '/home/lucas/Documents/luucycle/skills/luucycle'
md_files = [f for f in os.listdir(skill_dir) if f.endswith('.md')]

broken_links = []

for md_file in md_files:
    path = os.path.join(skill_dir, md_file)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find markdown links: [text](link)
    links = re.findall(r'\[.*?\]\((.*?)\)', content)

    for link in links:
        # Strip anchors for file checking
        target_file = link.split('#')[0]

        # We only care about local relative links, not http/https
        if target_file and not target_file.startswith(('http://', 'https://', 'mailto:')):
            target_path = os.path.join(skill_dir, target_file)
            if not os.path.exists(target_path):
                broken_links.append((md_file, link))

if broken_links:
    for src, link in broken_links:
        print(f"{src} -> {link} (BROKEN)")
else:
    print("All local links are valid!")
