import re

# Read the app.py file
with open('app.py', 'r') as f:
    content = f.read()

# Replace all cursor creations
content = re.sub(r'cursor = conn\.cursor\(dictionary=True\)', 'cursor = conn.cursor()', content)

# Replace all %s placeholders with ?
content = re.sub(r'= %s', '= ?', content)
content = re.sub(r', %s', ', ?', content)

# Write the updated content back to app.py
with open('app.py', 'w') as f:
    f.write(content)

print("Updated app.py successfully!")
