import sys

filepath = r"E:\New folder\security_app_final\vercel_dashboard\index.html"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

import re

# Remove the lock button in the header
lock_btn_pattern = r'<!-- Lock/Unlock System -->\s*<button id="toggleLockBtn"[^>]*>.*?</button>'
content = re.sub(lock_btn_pattern, '', content, flags=re.DOTALL)

# Also find and remove if it's not preceded by the comment
lock_btn_pattern_2 = r'<button id="toggleLockBtn"[^>]*>.*?</button>'
content = re.sub(lock_btn_pattern_2, '', content, flags=re.DOTALL)

# Remove the toggleAppLock function
toggle_app_lock_func = r'async function toggleAppLock\(\) \{.*?\n        \}\n'
content = re.sub(toggle_app_lock_func, '', content, flags=re.DOTALL)

# Remove the secret lock logic at the end
secret_lock_logic = r'// Secret Lock Button logic.*?\}\);'
content = re.sub(secret_lock_logic, '', content, flags=re.DOTALL)

# Remove the settings listener for is_locked completely
# Let's just find the block and remove it
settings_listener = r'// Listen to Settings document.*?\}\);'
content = re.sub(settings_listener, '', content, flags=re.DOTALL)


with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
print("Lock logic removed from index.html")
