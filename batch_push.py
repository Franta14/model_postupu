import os
import subprocess
import time

def run(cmd):
    print("Running:", cmd)
    subprocess.run(cmd, shell=True, check=True)

files = []
for root, _, filenames in os.walk('export'):
    for f in filenames:
        files.append(os.path.join(root, f).replace('\\', '/'))

print(f"Total files: {len(files)}")

chunk_size = 300
for i in range(0, len(files), chunk_size):
    chunk = files[i:i+chunk_size]
    print(f"Processing chunk {i//chunk_size + 1} of {len(files)//chunk_size + 1}")
    
    # Add files
    for f in chunk:
        run(f'git add "{f}"')
    
    # Commit
    run(f'git commit -m "Upload export files part {i//chunk_size + 1}"')
    
    # Push
    retry = 3
    while retry > 0:
        try:
            run('git push')
            break
        except subprocess.CalledProcessError:
            print("Push failed, retrying...")
            retry -= 1
            time.sleep(5)
            if retry == 0:
                print("Failed to push chunk, exiting.")
                exit(1)
