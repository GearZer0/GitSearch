import requests
import sys
import os
import re
import subprocess
import glob
import csv
import pathlib
from copy import deepcopy
import datetime
from pydriller import Git,Repository

GITHUB_HEADERS = {
    'user-agent': 'Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.193 Safari/537.36'
}

# checking if the parameter is correctly provided, alert if no parameter is present
if len(sys.argv) < 2:
    print("Usage: python {} https://github-file-url".format(sys.argv[0]))
    exit(0)


def search_github(url, github_headers=GITHUB_HEADERS):
    session = requests.Session()

    
    first_page = session.get(url, headers=github_headers)
    
    if(first_page.status_code == 403):
        raise Exception("Exceeded github api rate-limit")
    yield first_page.json()
    
    next_page = first_page
    while get_next_page(next_page) is not None:  
        try:
            next_page_url = next_page.links['next']['url']
            next_page = session.get(next_page_url, headers=github_headers)
            if(next_page.status_code == 403):
                raise Exception("Exceeded github api rate-limit")
            yield next_page.json()
        
        except KeyError:
            break
            
def get_next_page(page):
    return page if page.headers.get('link') != None else None


def get_possible_emails_and_names_from_commits(commits,login,name):
    possible_emails = []
    possible_names = []

    for commit in commits:
        commit_data = commit["commit"]
        commit_author = commit["author"]["login"] if commit["author"] else ""
        commit_committer = commit["committer"]["login"] if commit["committer"] else ""

        if(commit_author == login or commit_committer == login or commit_data["author"]["name"] == login or commit_data["author"]["name"] == name):
            possible_emails.append(commit_data["author"]["email"])
            if(commit_data["author"]["name"] != login):
                possible_names.append(commit_data["author"]["name"])
    
    possible_emails = list(dict.fromkeys(possible_emails))
    possible_emails = ",".join(possible_emails)

    possible_names = list(dict.fromkeys(possible_names))
    possible_names = ",".join(possible_names)
    return possible_emails, possible_names

def get_possible_emails_from_events(events,login,name):
    possible_emails = []
    for event in events:
        if(event["type"] == "PushEvent"):
            commits = event["payload"]["commits"]
            for commit in commits:
                if(commit["author"]["name"] == login or commit["author"]["name"] == name):
                    possible_emails.append(commit["author"]["email"])
    return possible_emails

# accesses github api to display user information
def getUserInfo(username):
    link = "https://api.github.com/users/{}".format(username)
    try:
        resp = requests.get(link)
        if(resp.status_code == 403):
            raise Exception("Exceeded github api rate-limit")
        resp = resp.json()
    except Exception as e:
        print("Failed to open {}".format(link))
        print("############### {} #################".format(e))
        return
    user_data = {
        "Login": resp.get('login'),
        "Name": resp.get('name'),
        "Email": resp.get('email'),
        "Created At": resp.get('created_at'),
        "Updated At": resp.get('updated_at'),
    }
    return user_data

def displayUserInfo(user_data):
    for key,value in user_data.items():
        print("{}: {}".format(key,value))

# accesses github api to display forks information
def getForksInfo(username,repository_name):
    link = "https://api.github.com/repos/{}/{}/forks".format(
        username, repository_name)
    try:
        forks = []
        # Iterate through pages
        for page_data in search_github(link):
            forks.extend(page_data)
    except Exception as e:
        print("Failed to open {}".format(link))
        print("############### {} #################".format(e))
        return
    print('Forks details')
    print('--------------------')
    # looping over contributors if more than one
    for fork in forks:
        # getting author username
        fork_url = fork.get('html_url')
        print(fork_url)

# accesses github api to display repository information
def getRepositoryInfo(username, repository_name):
    link = "https://api.github.com/repos/{}/{}".format(
        username, repository_name)
    try:
        resp = requests.get(link)
        if(resp.status_code == 403):
            raise Exception("Exceeded github api rate-limit")
        resp = resp.json()
    except Exception as e:
        print("Failed to open {}".format(link))
        print("############### {} #################".format(e))
        return
    print("Name: {}".format(resp.get('name')))
    print("Full Name: {}".format(resp.get('full_name')))
    print("Description: {}".format(resp.get('description')))
    print("Private: {}".format(resp.get('private')))
    print("Created At: {}".format(resp.get('created_at')))
    print("Updated At: {}".format(resp.get('updated_at')))
    print("Pushed At: {}".format(resp.get('pushed_at')))
    print("Number Of Forks: {}".format(resp.get('forks')))

    contributors_url = resp.get('contributors_url')
    return contributors_url



# function to check contributor data
def getContributorsList(contributors_url):
    try:
        resp = requests.get(contributors_url)
        if(resp.status_code == 403):
            raise Exception("Exceeded github api rate-limit")
        return resp.json()
    except Exception as e:
        print("Failed to open {}".format(contributors_url))
        print("############### {} #################".format(e))
        return

# function to check contributor data
def getContributorsInfo(contributors_url):
    contributors_list = getContributorsList(contributors_url)

    contributors_data = []
    for author in contributors_list:
        # getting author username
        author_username = author.get('login')
        contributors_data.append(getUserInfo(author_username))
    return contributors_data

# function to check last commit date, must have git installed
def getLatestCommitDate(username, repo_name):
    link = "https://github.com/{}/{}.git".format(
        username, repo_name)
    # cloning the repository
    subprocess.getoutput('git clone {}'.format(link))
    # going to the cloned folder and executing the log
    reverse = subprocess.getoutput(
        'cd {} && git log --reverse'.format(repo_name))
    # print(reverse)
    last_commit_date = re.findall(r'Date:(.+?)\n', reverse)
    last_commit_author = re.findall(r'Author:(.+?)\n', reverse)
    # finding the last commit date using regex
    if len(last_commit_date):
        print("Earliest Commit On: {}".format(last_commit_date[0].strip()))
        print("Author: {}".format(last_commit_author[0].strip()))
    else:
        print("No earliest commit date found!")

# function to get latest commit date for the input file


def getFileLatestCommitDate(repo_name, git_page_link):
    # parsing the actual file name
    file_path = git_page_link.split('/')[-1]
    print("File Name: {}".format(file_path))
    if file_path == "":
        return
    # going to the cloned folder and executing the log
    reverse = subprocess.getoutput(
        'cd ' + re.sub('/blob/.*','',repo_name) + ' && git log --reverse --pretty=format:"%an %ad" ' + file_path)
    # print(reverse)
    # finding the last commit date using regex
    print("Latest Commit Data: {}".format(reverse.split('\n')[0]))

def getRepoDataToCSV(repo_name):
    short_repo_name = re.sub('/blob/\w+','',repo_name)
    files = glob.glob(os.path.join(short_repo_name,"**"),recursive=True)
    file_objects = []
    gr = Git(short_repo_name)
    for file in files:
        file_obj = {}
        file_obj["file_path"] = file

        #file_obj["type"] = "dir" if os.path.isdir(file) else "file"
        if(not os.path.isdir(file)):
            p = pathlib.Path(file)
            internal_filename = str(pathlib.Path(*p.parts[1:]))

            commits = gr.get_commits_modified_file(internal_filename) # this return a list of commits hash
            for commit in Repository(short_repo_name, only_commits=commits).traverse_commits():
                file_obj_copy = deepcopy(file_obj)
                file_obj_copy["utc_datetime"] = commit.committer_date.astimezone(datetime.timezone.utc)
                file_obj_copy["commiter_name"]= commit.committer.name
                file_obj_copy["commiter_email"]= commit.committer.email
                file_obj_copy["msg"] = commit.msg.split("\n")[0]
                file_objects.append(file_obj_copy)

    with open(short_repo_name+".csv","w",newline='') as csv_output_file:
        writer = csv.DictWriter(csv_output_file,fieldnames=file_objects[0].keys())
        
        writer.writeheader()
        writer.writerows(file_objects)



if __name__ == "__main__":
    # putting the github file link in a variable
    git_page_link = sys.argv[1]
    # parsing the username and the repository from the input parameter
    matches = re.findall(r'github\.com/(.+?)/(.+?)((/.*)|$)', git_page_link)
    # parsing full repo link for single file
    matches2 = re.findall(r'github\.com/(.+?)/(.+)((/.*)|$)', git_page_link)

    # separating the username
    username = matches[0][0]
    # separating the repository name
    repo_name = matches[0][1]
    # separating the rest of the url (the file will be there)
    more_info = matches[0][2]
    # used for single file
    repo_name_full = matches2[0][1]

    if(not username or not repo_name):
        raise Exception("Failed to parse url")
    

    # collecting repository info and receiving contributor url
    print("Repository details")
    print("------------------")
    contributors_url = getRepositoryInfo(username, repo_name)
    # getting latest commit date
    getLatestCommitDate(username, repo_name)
    print()

    contributors_data_mapping = {}
    contributors_data = getContributorsInfo(contributors_url)

    try:
        commits_url = "https://api.github.com/repos/{}/{}/commits".format(username,repo_name)
        commits = []
        # Iterate through pages
        for page_data in search_github(commits_url):
            commits.extend(page_data)
        
        contributors_data_mapping = {}
        for cont in contributors_data:
            possible_emails, possible_names = get_possible_emails_and_names_from_commits(commits,cont["Login"],cont["Name"])
            cont["Name"] = cont["Name"] if cont["Name"] else possible_names
            cont["Email"] = cont["Email"] if cont["Email"] else possible_emails
            contributors_data_mapping[cont["Login"]] = deepcopy(cont)
    except Exception as e:
        print("Failed to enrich contributors data")
        print("############### {} #################".format(e))


    # collecting user info
    print("User details")
    print("-------------")
    if(username in contributors_data_mapping.keys()):
        displayUserInfo(contributors_data_mapping[username])
    else:
        displayUserInfo(getUserInfo(username))
    print()

    if (len(more_info) > 1):
        print()
        # getting latest commit date for the given file
        print('File details')
        print('-----------')
        getFileLatestCommitDate(repo_name_full, git_page_link)
    print()

    print('Contributor details')
    print('--------------------')
    for cont in contributors_data_mapping:
        displayUserInfo(contributors_data_mapping[cont])
        print()

    # getting forks info
    getForksInfo(username,repo_name)

    getRepoDataToCSV(repo_name)
