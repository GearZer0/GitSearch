import requests
import sys
import os
import re
import subprocess

# checking if the parameter is correctly provided, alert if no parameter is present
if len(sys.argv) < 2:
    print("Usage: python {} https://github-file-url".format(sys.argv[0]))
    exit(0)


# accesses github api to display user information
def getUserInfo(username):
    link = "https://api.github.com/users/{}".format(username)
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.193 Safari/537.36'
    }
    try:
        resp = requests.get(link, headers=headers).json()
    except:
        print("Failed to open {}".format(link))
        return
    print("Login: {}".format(resp.get('login')))
    print("Name: {}".format(resp.get('name')))
    print("Email: {}".format(resp.get('email')))
    print("Created At: {}".format(resp.get('created_at')))
    print("Updated At: {}".format(resp.get('updated_at')))


# accesses github api to display repository information
def getRepositoryInfo(username, repository_name):
    link = "https://api.github.com/repos/{}/{}".format(
        username, repository_name)
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.193 Safari/537.36'
    }
    try:
        resp = requests.get(link, headers=headers).json()
    except:
        print("Failed to open {}".format(link))
        return
    print("Name: {}".format(resp.get('name')))
    print("Full Name: {}".format(resp.get('full_name')))
    print("Description: {}".format(resp.get('description')))
    print("Private: {}".format(resp.get('private')))
    print("Created At: {}".format(resp.get('created_at')))
    print("Updated At: {}".format(resp.get('updated_at')))
    print("Pushed At: {}".format(resp.get('pushed_at')))
    contributors_url = resp.get('contributors_url')
    return contributors_url


# function to check contributor data
def getContributorsInfo(contributors_url):
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.193 Safari/537.36'
    }
    try:
        resp = requests.get(contributors_url, headers=headers).json()
    except:
        print("Failed to open {}".format(contributors_url))
        return
    print('Contributor details')
    print('--------------------')
    # looping over contributors if more than one
    for author in resp:
        # getting author username
        author_username = author.get('login')
        # using premade function to get author data
        getUserInfo(author_username)
        print("")


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
def getFileLatestCommitDate(username, repo_name, git_page_link):
    # parsing the actual file name
    file_path = git_page_link.split('/')[-1]
    print("File Name: {}".format(file_path))
    if file_path == "":
        return
    # going to the cloned folder and executing the log
    reverse = subprocess.getoutput(
        'cd {} && git log --reverse {} '.format(repo_name, file_path))
    # print(reverse)
    last_commit_date = re.findall(r'Date:(.+?)\n', reverse)
    last_commit_author = re.findall(r'Author:(.+?)\n', reverse)
    # finding the last commit date using regex
    if len(last_commit_date):
        print("Earliest Commit On: {}".format(last_commit_date[0].strip()))
        print("Author: {}".format(last_commit_author[0].strip()))
    else:
        print("No earliest commit date found!")



if __name__ == "__main__":
    # putting the github file link in a variable
    git_page_link = sys.argv[1]
    # parsing the username and the repository from the input parameter
    matches = re.findall(r'github\.com/(.+?)/(.+?)/', git_page_link)
    # separating the username
    username = matches[0][0]
    # separating the repository name
    repo_name = matches[0][1]
    # collecting user info
    print("User details")
    print("-------------")
    getUserInfo(username)
    # collecting repository info and receiving contributor url
    print("Repository details")
    print("------------------")
    contributors_url = getRepositoryInfo(username, repo_name)
    # getting latest commit date
    getLatestCommitDate(username, repo_name)
    # getting latest commit date for the given file
    print('File details')
    print('-----------')
    getFileLatestCommitDate(username, repo_name, git_page_link)
    
    # getting contributors list and their info
    getContributorsInfo(contributors_url)
 
