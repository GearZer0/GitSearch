import requests
import sys
import os
import stat
import shutil
import subprocess
import csv
import datetime
from collections import defaultdict
from prettytable import PrettyTable
from termcolor import colored
from pydriller import Repository

TOKENS = []
CURRENT_TOKEN_INDEX = 0

GITHUB_HEADERS = {
    'X-GitHub-Api-Version': "2022-11-28",
    'user-agent': 'Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.193 Safari/537.36'
}

if (len(TOKENS)):
    GITHUB_HEADERS['authorization'] = f"Bearer {TOKENS[CURRENT_TOKEN_INDEX]}"

COMBINING_OPTIONS = ['--combineall', '--combinerepo', '--combinefork']
EXPANDING_OPTIONS = ['--expandedsearch',
                     '--escontributors', '--esforkers', '--esuser']
COMBINING_OPTION = ""
EXPANDING_OPTION = ""
USER_FOR_EXPANDED_SEARCH = ""

all_repos = []
users = []

# checking if the parameter is correctly provided, alert if no parameter is present
if len(sys.argv) < 2 or sys.argv[1] == '--help' or sys.argv[1] == '-h':
    print()
    print(colored("usage:\n", 'green'))
    print(colored("\ngenerate CSV report for every branch of each repo:", 'magenta'))
    print(colored(
        "\tpython {} https://github.com/user/repo https://github.com/user0/repo ...".format(sys.argv[0]), 'yellow'), colored("[option]", "red"))
    print(
        colored("\tpython {} path/to/repo-links-file.txt".format(sys.argv[0]), 'yellow'), colored("[option]", "red"))
    print(colored("\n--combineall", "red"),
          colored("\t\tcombine all repos with their forks as well as their branches into one CSV", 'magenta'))
    print(colored("--combinerepo", "red"),
          colored("\t\tcombine all repos with their branches into one CSV", 'magenta'))
    print(colored("--combinefork", "red"),
          colored("\t\tcombine forks of each repo with their branches into CSV", 'magenta'))
    print(colored("--expandedsearch", "red"),
          colored("\tscan each branch of every repo of the each contributor and the forker user of the input repo to get emails from the commit history", 'magenta'))
    print(colored("--esforkers", "red"),
          colored("\t\tscan each branch of every repo of the each forker user of the input repo to get emails from the commit history", 'magenta'))
    print(colored("--escontributors", "red"),
          colored("\tscan each branch of every repo of the each contributor user of the input repo to get emails from the commit history", 'magenta'))
    print(colored("--esuser", "red"), colored("username", "yellow"),
          colored("\tscan each branch of every repo of the exact user to get emails from the commit history", 'magenta'))
    print()
    exit(0)


def getReposFromTXT(path):
    file = open(path, "r").read()
    return list(filter(None, file.split("\n")))


# Yield pages from GitHub API (uses make_request_to_github function)


def search_github(url):
    session = requests.Session()

    # first_page = session.get(url, headers=GITHUB_HEADERS)
    first_page = make_request_to_github(url, returnRaw=True)

    if (first_page == None):
        raise Exception("Exceeded GitHub API rate-limit")
    yield first_page.json()

    next_page = first_page
    while get_next_page(next_page) is not None:
        try:
            next_page_url = next_page.links['next']['url']
            next_page = make_request_to_github(next_page_url, returnRaw=True)
            if (next_page == None):
                raise Exception("Exceeded GitHub API rate-limit")
            yield next_page.json()

        except KeyError:
            break


def get_next_page(page):
    return page if page.headers.get('link') != None else None


# GitHub API request helper - tokens setting and error handling


def make_request_to_github(url, returnRaw=False):
    global CURRENT_TOKEN_INDEX
    while True:
        response = requests.get(
            url, headers=GITHUB_HEADERS)
        if (response.status_code == 403):
            if (CURRENT_TOKEN_INDEX+1 < len(TOKENS)):
                CURRENT_TOKEN_INDEX += 1
                print(colored(
                    f"[INFO] Switching to Token {CURRENT_TOKEN_INDEX+1} ...", 'magenta'))
                GITHUB_HEADERS['authorization'] = f"Bearer {TOKENS[CURRENT_TOKEN_INDEX]}"
                continue
            else:
                print(colored("[ERROR] Exceeded GitHub API rate-limit", 'red'))
                return None
        else:
            if (returnRaw):
                return response
            response = response.json()
            return response


# Write repo data to CSV based on repo_link parameter


def getRepoDataToCSV(repo_link, isFork=False, originalRepoUsername=None, originalRepoName=None):
    username, repo_name = extractRepoAndUserFromURL(repo_link)
    clone_path = './bare_clones/' + f'{username}__{repo_name}'
    print(colored(
        f"[INFO] Cloning {repo_link} Repo{' (Fork)' if isFork else ''}...", 'magenta'))
    subprocess.getoutput(
        'git clone --mirror {} {}'.format(repo_link, clone_path))
    subprocess.getoutput(
        f'git config --add safe.directory {clone_path}')
    print(colored("[DONE]", 'green'))
    out = subprocess.getoutput(
        'cd {} && git branch'.format(clone_path))
    branches = [b.strip('* ') for b in out.splitlines()]
    if isFork:
        all_repos[-1]["forks"][-1]["fork_link"] = repo_link
        all_repos[-1]["forks"][-1]["branches"] = len(branches)
    else:
        all_repos[-1]["branches"] = len(branches)
    commits = []
    for branch in branches:
        subprocess.getoutput(
            "cd {} && git symbolic-ref HEAD refs/heads/'{}'".format(clone_path, branch))
        for commit in Repository(clone_path).traverse_commits():
            all_repos[-1]["contributors"][commit.author.email] = {"email": commit.author.email, "name": commit.author.name,
                                                                  "commit_count": all_repos[-1]["contributors"][commit.author.email]["commit_count"] + 1 if all_repos[-1]["contributors"][commit.author.email] else 1, "branches": list(all_repos[-1]["contributors"][commit.author.email]["branches"]) + [branch] if branch not in list(all_repos[-1]["contributors"][commit.author.email]["branches"]) else all_repos[-1]["contributors"][commit.author.email]["branches"]}
            for file in commit.modified_files:
                commits.append({"branch": branch, "username": username, "repo_name": repo_name, "modified_file": file.filename, "hash": commit.hash,
                                "author_name": commit.author.name, "author_email": commit.author.email, "committer_name": commit.committer.name, "committer_email": commit.committer.email, "commit_date_utc": commit.committer_date.astimezone(datetime.timezone.utc), "msg": commit.msg, "full_path": file.new_path, "change_type": file.change_type.name})
    if (not isFork):
        all_repos[-1]["earliest_commit_date"] = commits[0]["commit_date_utc"].astimezone(
            datetime.timezone.utc)

    pathToCSV = f"reports/{originalRepoUsername}__{originalRepoName}/forks/{username}__{repo_name}.csv" if isFork else f"reports/{username}__{repo_name}/{username}__{repo_name}.csv"
    os.makedirs(os.path.dirname(pathToCSV), exist_ok=True)
    print(colored("[INFO] Getting Commit Data to CSV...", 'magenta'))
    with open(pathToCSV, "w", newline='', encoding="utf-8") as csv_output_file:
        writer = csv.DictWriter(
            csv_output_file, fieldnames=['branch', 'modified_file', 'hash', 'author_name', 'author_email', 'committer_name', 'committer_email', 'commit_date_utc', 'msg', 'full_path', 'change_type'], extrasaction='ignore')

        writer.writeheader()
        writer.writerows(commits)

    if COMBINING_OPTION == "combineall":
        combine(commits, "reports/all.csv")
    elif COMBINING_OPTION == "combinerepo" and not isFork:
        combine(commits, "reports/all_repo.csv")
    elif COMBINING_OPTION == "combinefork" and isFork:
        combine(
            commits, f"reports/{originalRepoUsername}__{originalRepoName}/forks/all_forks.csv")

    print(colored("[DONE]\n", 'green'))
    try:
        if not os.access('./bare_clones/', os.W_OK):
            os.chmod('./bare_clones/', stat.S_IWRITE)
        shutil.rmtree('./bare_clones/', ignore_errors=True)
    except:
        print(colored(
            "[ERROR] Can't Delete Cloned Repo. Please Ensure You Run This Script in Admin Privileges", 'red'))


# Generate combined CSV files based on provided combining option


def combine(commits, path):
    file_exists = os.path.isfile(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", newline='', encoding="utf-8") as csv_output_file:
        writer = csv.DictWriter(
            csv_output_file, fieldnames=['owner/repo', 'username', 'repo_name', 'branch', 'modified_file', 'hash', 'author_name', 'author_email', 'committer_name', 'committer_email', 'commit_date_utc', 'msg', 'full_path', 'change_type'])

        if not file_exists:
            writer.writeheader()
        for commit in commits:
            commit["owner/repo"] = f'{commit["username"]}/{commit["repo_name"]}'
            writer.writerow(commit)


# Write fork data to CSV based on repo_link parameter (uses getRepoDataToCSV function)


def getForkDataToCSV(repo_link):
    print(colored(f"[INFO] Getting Fork Data for {repo_link}...", 'magenta'))
    forks = []
    username, repo_name = extractRepoAndUserFromURL(repo_link)
    for page_data in search_github("https://api.github.com/repos/{}/{}/forks".format(
            username, repo_name)):
        forks.extend(page_data)
    forks = [{"html_url": fork["html_url"], "created_at": fork["created_at"],
              "updated_at": fork["updated_at"], "pushed_at": fork["pushed_at"]} for fork in forks]
    print(colored("[DONE]\n", 'green'))
    for repo in forks:
        all_repos[-1]["forks"].append({"created_at": repo["created_at"],
                                       "updated_at": repo["updated_at"], "pushed_at": repo["pushed_at"]})
        getRepoDataToCSV(repo["html_url"], True, username, repo_name)


# Write all users of a repo to CSV file


def write_users_data_to_CSV(users):
    path = './reports/users.csv'
    file_exists = os.path.isfile(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", newline='', encoding="utf-8") as csv_output_file:
        writer = csv.DictWriter(
            csv_output_file, extrasaction='ignore', fieldnames=['username', 'repo_name', 'email', 'name', 'location', 'company', 'website', 'bio', 'twitter', 'user_created_at', 'user_updated_at', 'repo', 'fork', 'forked_from', 'repo_created_at', 'branches'])

        if not file_exists:
            writer.writeheader()
        writer.writerows(users)


def write_emails_data_to_CSV(username, repo, emails):
    path = './reports/emails.csv'
    file_exists = os.path.isfile(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", newline='', encoding="utf-8") as csv_output_file:
        writer = csv.DictWriter(
            csv_output_file, fieldnames=['username', 'repo', 'emails'])

        if not file_exists:
            writer.writeheader()
        writer.writerow(
            {"username": username, "repo": repo, "emails": emails})


def extractRepoAndUserFromURL(link):
    matches = link.split('github.com')[1].split('/')
    username = matches[1]
    repo_name = matches[2]
    return username, repo_name


# Clone original of all repos and their forks with all branches


def cloneAllRepos():
    wd = os.getcwd()
    for repo in all_repos:
        username, repo_name = extractRepoAndUserFromURL(repo["repo_link"])
        clone_name = f'{username}__{repo_name}'
        mainPath = f"clones/{clone_name}"
        forksPath = f"{mainPath}/forks"
        # os.makedirs(os.path.dirname(mainPath), exist_ok=True)
        os.makedirs(forksPath, exist_ok=True)
        os.chdir(mainPath)
        out = subprocess.getoutput(
            f'git clone {repo["repo_link"]} {clone_name}')
        os.chdir(clone_name)
        branches = subprocess.getoutput(
            f'git branch -r')
        branches = list(map(lambda rb: rb[7:], [b.strip(
            '* ') for b in branches.splitlines()][2:]))
        for branch in branches:
            subprocess.getoutput(
                f"git branch '{branch}'")
        print(colored(f"[INFO] {out}", 'magenta'))
        os.chdir(wd)
        for fork in repo["forks"]:
            f_username, f_repo_name = extractRepoAndUserFromURL(
                fork["fork_link"])
            fork_clone_name = f'{f_username}__{f_repo_name}'
            os.chdir(forksPath)
            out = subprocess.getoutput(
                f'git clone {fork["fork_link"]} {fork_clone_name}')
            os.chdir(fork_clone_name)
            branches = subprocess.getoutput(
                f'git branch -r')
            branches = list(map(lambda rb: rb[7:], [b.strip(
                '* ') for b in branches.splitlines()][2:]))
            for branch in branches:
                subprocess.run(
                    f"git branch '{branch}'", shell=True)
            print(colored(f"[INFO] {out}", 'magenta'))
            os.chdir(wd)


# Report helpful information about repo, forks, users, etc. on console


def printRepoAndUserData(repo_link):
    print(colored(
        f'\n\n\n----------------------------------------{repo_link.upper()}----------------------------------------\n\n\n', 'red'))
    username, repo_name = extractRepoAndUserFromURL(repo_link)
    user_resp = make_request_to_github(
        f'https://api.github.com/users/{username}')
    if (user_resp == None):
        print(colored("[ERROR] Exceeded GitHub API rate-limit", 'red'))
    else:
        user_table = PrettyTable(
            ["username", "email", "name", "location", "company", "website", "bio", "twitter", "created at", "updated at"], max_width=15)
        user_table.add_row([user_resp["login"],
                            user_resp["email"], user_resp["name"], user_resp["location"], user_resp["company"], user_resp["blog"], user_resp["bio"].replace("\r\n", " ") if user_resp["bio"] else None, user_resp["twitter_username"], user_resp["created_at"], user_resp["updated_at"]])
        print(colored('\n--------------------OWNER DATA--------------------\n', 'green'))
        print(user_table)
    repo_resp = make_request_to_github(
        f"https://api.github.com/repos/{username}/{repo_name}")
    if (repo_resp == None):
        print(colored("[ERROR] Exceeded GitHub API rate-limit", 'red'))
    else:
        repo_table = PrettyTable(
            ["name", "description", "fork", "created at", "updated at", "pushed at", "earliest commit", "branches", "forks"])
        repo_table._max_width = {"name": 15, "description": 15, "fork": 10,
                                 "created at": 20, "updated at": 20, "pushed at": 20, "earliest commit": 20, "branches": 10, "forks": 10}
        repo_table.add_row([repo_resp["full_name"], repo_resp["description"], repo_resp["fork"], repo_resp["created_at"],
                            repo_resp["updated_at"], repo_resp["pushed_at"], all_repos[-1]["earliest_commit_date"], all_repos[-1]["branches"], repo_resp["forks"]])
        print(colored('\n--------------------REPO DATA--------------------\n', 'green'))
        print(repo_table)
    users.append({"username": user_resp["login"], "repo_name": f"{username}/{repo_name}", "email": user_resp["email"], "name": user_resp["name"], "location": user_resp["location"], "company": user_resp["company"],
                  "website": user_resp["blog"], "bio": user_resp["bio"], "twitter": user_resp["twitter_username"], "user_created_at": user_resp["created_at"], "user_updated_at": user_resp["updated_at"], "repo": repo_link, "fork": repo_resp["fork"], "forked_from": repo_resp["parent"]["html_url"] if repo_resp["fork"] else None, "repo_created_at": repo_resp["created_at"], "branches": all_repos[-1]["branches"], "expanded_search": False})
    contributors_resp = make_request_to_github(
        repo_resp["contributors_url"])
    if (contributors_resp == None):
        print(colored("[ERROR] Exceeded GitHub API rate-limit", 'red'))
    else:
        contributors_table = PrettyTable(
            ["username", "email", "name", "location", "company", "website", "bio", "twitter", "created at", "updated at"], max_width=15)
        for user in contributors_resp:
            contributor_user_resp = make_request_to_github(
                user["url"])
            if (contributor_user_resp == None):
                print(colored("[ERROR] Exceeded GitHub API rate-limit", 'red'))
            else:
                users.append({"username": contributor_user_resp["login"], "repo_name": f"{username}/{repo_name}", "email": contributor_user_resp["email"], "name": contributor_user_resp["name"], "location": contributor_user_resp["location"], "company": contributor_user_resp["company"],
                              "website": contributor_user_resp["blog"], "bio": contributor_user_resp["bio"], "twitter": contributor_user_resp["twitter_username"], "user_created_at": contributor_user_resp["created_at"], "user_updated_at": contributor_user_resp["updated_at"], "repo": repo_link, "fork": repo_resp["fork"], "forked_from": repo_resp["parent"]["html_url"] if repo_resp["fork"] else None, "repo_created_at": repo_resp["created_at"], "branches": all_repos[-1]["branches"], "expanded_search": True if EXPANDING_OPTION != "esforkers" else False})
                contributors_table.add_row([contributor_user_resp["login"],
                                            contributor_user_resp["email"], contributor_user_resp["name"], contributor_user_resp["location"], contributor_user_resp["company"], contributor_user_resp["blog"], contributor_user_resp["bio"].replace("\r\n", " ") if contributor_user_resp["bio"] else None, contributor_user_resp["twitter_username"], contributor_user_resp["created_at"], contributor_user_resp["updated_at"]])
        print(colored(
            '\n--------------------CONTRIBUTORS DATA (GITHUB)--------------------\n', 'green'))
        print(contributors_table)
    commit_contributors_table = PrettyTable(
        ["email", "name", "commit count"], max_width=45)
    for cc in all_repos[-1]["contributors"].items():
        users.append({"username": None, "repo_name": f"{username}/{repo_name}", "email": all_repos[-1]["contributors"][cc[0]]["email"], "name": all_repos[-1]["contributors"][cc[0]]["name"], "company": None,
                      "bio": None, "user_created_at": None, "user_updated_at": None, "repo": repo_link, "fork": repo_resp["fork"], "forked_from": repo_resp["parent"]["html_url"] if repo_resp["fork"] else None, "repo_created_at": repo_resp["created_at"], "branches": all_repos[-1]["branches"]})
        commit_contributors_table.add_row(
            [all_repos[-1]["contributors"][cc[0]]["email"], all_repos[-1]["contributors"][cc[0]]["name"], all_repos[-1]["contributors"][cc[0]]["commit_count"]])
    print(colored(
        '\n--------------------CONTRIBUTORS DATA (COMMIT)--------------------\n', 'green'))
    print(commit_contributors_table)
    forks_table = PrettyTable(
        ["fork url", "fork date", "branches", "username", "email", "name", "location", "company", "website", "bio", "twitter", "created at", "updated at"], max_width=10)
    for fork in all_repos[-1]["forks"]:
        username, repo_name = extractRepoAndUserFromURL(fork["fork_link"])
        fork_user_resp = make_request_to_github(
            f'https://api.github.com/users/{username}')
        if (fork_user_resp == None):
            print(colored("[ERROR] Exceeded GitHub API rate-limit", 'red'))
        else:
            users.append({"username": fork_user_resp["login"], "repo_name": f"{username}/{repo_name}", "email": fork_user_resp["email"], "name": fork_user_resp["name"], "location": fork_user_resp["location"], "company": fork_user_resp["company"],
                          "website": fork_user_resp["blog"], "bio": fork_user_resp["bio"], "twitter": fork_user_resp["twitter_username"], "user_created_at": fork_user_resp["created_at"], "user_updated_at": fork_user_resp["updated_at"], "repo": fork["fork_link"], "fork": True, "forked_from": repo_link, "repo_created_at": fork["created_at"], "branches": fork["branches"], "expanded_search": True if EXPANDING_OPTION != "escontributors" else False})
            forks_table.add_row([fork["fork_link"], fork["created_at"], fork["branches"], fork_user_resp["login"],
                                fork_user_resp["email"], fork_user_resp["name"], fork_user_resp["location"], fork_user_resp["company"], fork_user_resp["blog"], fork_user_resp["bio"].replace("\r\n", " ") if fork_user_resp["bio"] else None, fork_user_resp["twitter_username"], fork_user_resp["created_at"], fork_user_resp["updated_at"]])
    print(colored(
        '\n--------------------FORK DATA--------------------\n', 'green'))
    print(forks_table)
    print(colored('\n\n\n--------------------------------------------------------------------------------------------------------------------------------------------\n\n\n', 'red'))
    if repo_resp["fork"]:
        print(colored(
            f'\n\n\n--------------------------------------------------PARENT REPO ({repo_resp["parent"]["full_name"]})--------------------------------------------------\n\n\n', 'yellow'))
        subprocess.run(
            f'python3 {sys.argv[0]} {repo_resp["parent"]["html_url"]}', shell=True)
        print(colored(
            f'\n\n\n------------------------------------------------------------------------------------------------------------------------------------------------------\n\n\n', 'yellow'))
    write_users_data_to_CSV(users)


def get_emails_from_users_repos():
    print(colored(
        "[INFO] Getting Emails from Repos", 'magenta'))
    regex = "\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,6}\\b"
    toLowerCaseExpression = "{print tolower($0)}"
    wd = os.getcwd()
    usernames = []
    repos = []
    emails = []
    if USER_FOR_EXPANDED_SEARCH:
        usernames = [USER_FOR_EXPANDED_SEARCH]
    else:
        for user in users:
            usernames.append(
                user["username"]) if user["username"] and user["expanded_search"] == True and user["username"] not in usernames else True

    for username in usernames:
        for page_data in search_github(f"https://api.github.com/users/{username}/repos"):
            repos.extend(page_data)
        for repo in repos:
            repo_emails = []
            u = repo["owner"]["login"]
            r = repo["name"]
            clone_path = 'bare_clones/' + f'{u}__{r}'
            print(colored(
                f"[INFO] Cloning {repo['html_url']} Repo...", 'magenta'))
            subprocess.getoutput(
                f'git clone --mirror {repo["html_url"]} {clone_path}')
            subprocess.getoutput(
                f'git config --add safe.directory {clone_path}')
            print(colored("[DONE]", 'green'))
            os.chdir(clone_path)
            out = subprocess.getoutput('git branch')
            branches = [b.strip('* ') for b in out.splitlines()]
            for branch in branches:
                emails_output = subprocess.getoutput(
                    "git symbolic-ref HEAD refs/heads/'{}' && git shortlog -sea | grep -E -o '{}' | awk '{}' | uniq | grep -wv 'users.noreply.github.com' && git shortlog -sec | grep -E -o '{}' | awk '{}' | uniq | grep -wv 'users.noreply.github.com'".format(branch, regex, toLowerCaseExpression, regex, toLowerCaseExpression))
                emails.extend(emails_output.split('\n'))
                emails = list(set(emails))
                repo_emails.extend(emails_output.split('\n'))
                repo_emails = list(set(repo_emails))
            os.chdir(wd)
            emails_table = PrettyTable(
                ["username", "repo", "emails"], max_width=45)
            emails_table.add_row([u, r, repo_emails])
            print(emails_table)
            print(colored(
                f"[INFO] Getting Email Data to CSV", 'magenta'))
            write_emails_data_to_CSV(u, r, repo_emails)
            print(colored("[DONE]", 'green'))
            try:
                if not os.access('./bare_clones/', os.W_OK):
                    os.chmod('./bare_clones/', stat.S_IWRITE)
                shutil.rmtree('./bare_clones/', ignore_errors=True)
            except:
                print(colored(
                    "[ERROR] Can't Delete Cloned Repo. Please Ensure You Run This Script in Admin Privileges", 'red'))
    print(colored(
        "[DONE] Getting Emails from Repos Completed", 'green'))


if __name__ == "__main__":
    print(colored("[INFO] Script Started", 'magenta'))
    arg = sys.argv[1]
    given_combining_options = list(
        filter(lambda o: o in COMBINING_OPTIONS, sys.argv))
    given_expanding_options = list(
        filter(lambda o: o in EXPANDING_OPTIONS, sys.argv))
    if len(given_combining_options):
        COMBINING_OPTION = given_combining_options[0][2:]
    if len(given_expanding_options):
        EXPANDING_OPTION = given_expanding_options[0][2:]
        if (EXPANDING_OPTION == 'esuser'):
            USER_FOR_EXPANDED_SEARCH = sys.argv[sys.argv.index('--esuser') + 1]
    repo_links = []
    if (not arg.startswith('https://') and arg.endswith('.txt')):
        repo_links = getReposFromTXT(arg)
    else:
        repo_links = list(
            filter(lambda o: 'github.com' in o, sys.argv[1:]))
    for i, repo in enumerate(repo_links):
        username, repo_name = extractRepoAndUserFromURL(repo)
        repo = f"https://github.com/{username}/{repo_name}"
        def recursive_dd(): return defaultdict(recursive_dd)
        all_repos.append(
            {"repo_link": repo, "forks": [], "contributors": recursive_dd()})
        getRepoDataToCSV(repo)
        getForkDataToCSV(repo)
        printRepoAndUserData(repo)
    print(colored("[DONE] All Reports Generated\n", 'green'))
    print(colored("[INFO] Cloning Original of All Repos...\n", 'magenta'))
    cloneAllRepos()
    if EXPANDING_OPTION:
        get_emails_from_users_repos()
