# -*- coding: utf-8 -*-
# !/usr/bin/python3

# python3 -m pip install yagmail tweepy selenium pdf2image --no-cache-dir
# sudo apt install poppler-utils -y
import json
import os
import datetime
import shutil
import urllib.request
import tweepy
import yagmail
import pdf2image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


def get911(key):
    with open('/home/pi/.911') as f:
        data = json.load(f)
    return data[key]


CONSUMER_KEY = get911('TWITTER_FIMDOCS_CONSUMER_KEY')
CONSUMER_SECRET = get911('TWITTER_FIMDOCS_CONSUMER_SECRET')
ACCESS_TOKEN = get911('TWITTER_FIMDOCS_ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = get911('TWITTER_FIMDOCS_ACCESS_TOKEN_SECRET')
EMAIL_USER = get911('EMAIL_USER')
EMAIL_APPPW = get911('EMAIL_APPPW')
EMAIL_RECEIVER = get911('EMAIL_RECEIVER')

auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)


def getLastTweetedPost():
    try:
        with open('log.json') as inFile:
            data = json.load(inFile)[0]
        return data["date"], data["title"], data["href"]
    except Exception:
        return "", "", ""


def getPosts():
    # Get last tweeted post date and title
    lastDate, lastTitle, lastHref = getLastTweetedPost()

    # Get Documents Page
    browser.get("https://www.fim-moto.com/en/documents")

    # Wait for documents to load
    documents = WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "documents")))
    documents = documents.find_elements(By.CLASS_NAME, "card-body")

    # Go through each card
    tmpDocuments = []
    for card in documents:
        _, cardTitle, cardDate = card.find_elements(By.TAG_NAME, "p")
        cardTitle, cardDate = cardTitle.text, cardDate.text
        cardHref = card.find_element(By.TAG_NAME, "a").get_attribute("href")

        # Change date from MM/DD/YYYY to YYYY/MM/DD
        cardDate = datetime.datetime.strptime(cardDate, "%m/%d/%Y").strftime("%Y/%m/%d")
        tmpDocuments.append({"date": cardDate, "title": cardTitle, "href": cardHref})

    # Sort documents by date, newest to older
    if tmpDocuments[0]["date"] < tmpDocuments[-1]["date"]:
        print("Reverse Documents")
        tmpDocuments = reversed(tmpDocuments)

    # Go through each card
    newPosts = []
    for card in tmpDocuments:
        cardTitle, cardDate, cardHref = card["title"], card["date"], card["href"]

        # Check if post is valid ? Add to new posts : break
        if cardDate >= lastDate and cardTitle != lastTitle and cardHref != lastHref:
            newPosts.append({"date": cardDate, "title": cardTitle, "href": cardHref})
        else:
            break

    return newPosts


def getScreenshots(pdfHref):
    try:
        # Reset tmpFolder
        if os.path.exists(tmpFolder):
            shutil.rmtree(tmpFolder)
        os.mkdir(tmpFolder)

        # Download PDF
        pdfFile = os.path.join(tmpFolder, "tmp.pdf")
        urllib.request.urlretrieve(pdfHref, pdfFile)

        # Check what OS
        if os.name == "nt":
            pages = pdf2image.convert_from_path(poppler_path=r"poppler-win\Library\bin", pdf_path=pdfFile)
        else:
            pages = pdf2image.convert_from_path(pdf_path=pdfFile)

        # Save the first four pages
        for idx, page in enumerate(pages[0:4]):
            jpgFile = os.path.join(tmpFolder, "tmp_" + str(idx) + ".jpg")
            page.save(jpgFile)
        hasPics = True
    except Exception:
        print("Failed to screenshot")
        hasPics = False

    return hasPics


def tweet(tweetStr, hasPics):
    try:
        media_ids = []
        if hasPics:
            imageFiles = sorted([file for file in os.listdir(tmpFolder) if file.split(".")[-1] == "jpg"])
            media_ids = [api.media_upload(os.path.join(tmpFolder, image)).media_id_string for image in imageFiles]

        api.update_status(status=tweetStr, media_ids=media_ids)
        print("Tweeted")
    except Exception as ex:
        print("Failed to Tweet")
        yagmail.SMTP(EMAIL_USER, EMAIL_APPPW).send(EMAIL_RECEIVER, "Failed to Tweet - " + os.path.basename(__file__), str(ex) + "\n\n" + tweetStr)


def favTweets(tags, numbTweets):
    tags = tags.replace(" ", " OR ")
    tweets = tweepy.Cursor(api.search_tweets, q=tags).items(numbTweets)
    tweets = [tw for tw in tweets]

    for tw in tweets:
        try:
            tw.favorite()
            print(str(tw.id) + " - Like")
        except Exception as e:
            print(str(tw.id) + " - " + str(e))
            pass

    return True


def batchDelete():
    print("Deleting all tweets from the account @" + api.verify_credentials().screen_name)
    for status in tweepy.Cursor(api.user_timeline).items():
        try:
            api.destroy_status(status.id)
        except Exception:
            pass


def main():
    # Get latest posts
    newPosts = list(reversed(getPosts()))

    # Set hashtags
    hashtags = "#FIM #FIMfamily #GrandPrix #MotoGP"

    # Go through each new post
    for post in newPosts:
        # Get post info
        postTitle, postDate, postHref = post["title"], post["date"], post["href"]
        print(postTitle)
        print(postDate)

        # Get PDF link
        browser.get(postHref)
        pdfHref = browser.find_element(By.CLASS_NAME, "news-infos").find_element(By.TAG_NAME, "a").get_attribute("href")

        # Screenshot DPF
        hasPics = getScreenshots(pdfHref)

        # Tweet!
        tweet(postTitle + "\n" + "Published at: " + postDate + "\n\n" + pdfHref + "\n\n" + hashtags, hasPics)

        # Save log
        with open("log.json") as inFile:
            data = list(reversed(json.load(inFile)))
            data.append(post)
        with open("log.json", "w") as outFile:
            json.dump(list(reversed(data)), outFile, indent=2)

        print()

    # Get tweets -> Like them
    favTweets(hashtags, 5)


if __name__ == "__main__":
    print("----------------------------------------------------")
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    headless = True
    options = Options()
    options.headless = headless
    service = Service("/home/pi/geckodriver")
    # service = Service(r"C:\Users\xhico\OneDrive\Useful\geckodriver.exe")
    browser = webdriver.Firefox(service=service, options=options)

    # Set temp folder
    tmpFolder = r"tmp"

    try:
        main()
    except Exception as ex:
        print(ex)
        yagmail.SMTP(EMAIL_USER, EMAIL_APPPW).send(EMAIL_RECEIVER, "Error - " + os.path.basename(__file__), str(ex))
    finally:
        if headless:
            browser.close()
            print("Close")
        print("End")
