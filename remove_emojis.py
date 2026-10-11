import codecs
import os

def remove_emojis(filepath):
    try:
        with codecs.open(filepath, 'r', 'utf-8') as f:
            text = f.read()
    except Exception as e:
        return

    allowed_high_ords = {8364, 8377, 8211, 8212, 8216, 8217, 8218, 8219, 8220, 8221, 8226}
    clean_text = []
    for c in text:
        o = ord(c)
        if o > 1000 and o not in allowed_high_ords:
            continue
        clean_text.append(c)
        
    new_text = "".join(clean_text)
    
    if new_text != text:
        with codecs.open(filepath, 'w', 'utf-8') as f:
            f.write(new_text)
        print(f"Removed emojis from {filepath}")

for root, dirs, files in os.walk('.'):
    if '.git' in root or '.venv' in root or '__pycache__' in root:
        continue
    for file in files:
        if file.endswith('.html') or file.endswith('.py') or file.endswith('.md'):
            remove_emojis(os.path.join(root, file))
