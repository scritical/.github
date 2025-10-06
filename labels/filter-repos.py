import json
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("filename", type=str, help="input JSON filename")
parser.add_argument("output_filename", type=str, help="output txt filename")
args = parser.parse_args()
with open(args.filename) as f:
    data = json.load(f)

# the .github repo doesn't appear somehow
repos = ["scritical/.github"]

# remove archived repos
# or ones with the 'paper' tag
for d in data["data"]["organization"]["repositories"]["nodes"]:
    if not d["isArchived"]:
        topics = [t["topic"]["name"] for t in d["repositoryTopics"]["nodes"]]
        if "paper" not in topics:
            repoName = d["nameWithOwner"]
            if repoName not in repos:
                repos.append(repoName)

# write out the list
with open(args.output_filename, mode="w") as f:
    f.writelines("\n".join(repos) + "\n")
