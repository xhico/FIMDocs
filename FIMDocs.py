# -*- coding: utf-8 -*-
# !/usr/bin/python3

# python3 -m pip install tweepy selenium pyshorteners python-dateutil --no-cache-dir
import json
import os
import datetime
import tweepy
import yagmail
import pyshorteners
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
    with open('log.json') as inFile:
        data = json.load(inFile)
    return data["date"], data["title"], data["href"]


def getPosts():
    # Get last tweeted post date and title
    lastDate, lastTitle, lastHref = getLastTweetedPost()

    # Get Documents Page
    browser.get("https://www.fim-moto.com/en/documents")

    # Wait for documents to load
    documents = WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "documents")))

    # Go through each card
    newPosts = []
    cards = documents.find_elements(By.CLASS_NAME, "card-body")
    for card in cards:
        _, cardTitle, cardDate = card.find_elements(By.TAG_NAME, "p")
        cardTitle = cardTitle.text
        cardDate = cardDate.text
        cardHref = card.find_element(By.TAG_NAME, "a").get_attribute("href")

        # Change date from MM/DD/YYYY to YYYY/MM/DD
        cardDate = datetime.datetime.strptime(cardDate, "%m/%d/%Y").strftime("%Y/%m/%d") + " " + datetime.datetime.today().strftime("%Hh%M")

        # Check
        if cardDate.split(" ")[0] == lastDate.split(" ")[0] and cardTitle == lastTitle and cardHref == lastHref:
            break

        # Add to new posts
        newPosts.append({"date": cardDate, "title": cardTitle, "href": cardHref})

    return reversed(newPosts)


def tweet(tweetStr):
    api.update_status(tweetStr)
    print("Tweeted - " + tweetStr)

    return True


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


def main():
    # Get last post
    newPosts = getPosts()
    hashtags = "#FIM #FIMfamily #GrandPrix #MotoGP #Motorsports #Racing #Motorcycling"

    # Go through each new post
    for post in newPosts:
        cardTitle, cardDate, cardHref = post["title"], post["date"], post["href"]

        # Get PDF link
        browser.get(cardHref)
        pdfHref = browser.find_element(By.CLASS_NAME, "news-infos").find_element(By.TAG_NAME, "a").get_attribute("href")

        try:
            # TinyURL pdfHref and cardHref
            pdfHref = type_tiny.tinyurl.short(pdfHref)
            cardHref = type_tiny.tinyurl.short(cardHref)
        except Exception:
            break

        # Tweet!
        tweet(cardTitle + "\n\n" + "PDF " + pdfHref + "\n" + "URL " + cardHref + "\n\n" + "Published at: " + cardDate + "\n" + hashtags)

        # Save as last post
        with open('log.json', 'w') as outfile:
            json.dump(post, outfile, indent=4)

    # Get tweets -> Like them
    favTweets(hashtags, 10)


if __name__ == "__main__":
    print("----------------------------------------------------")
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    headless = True
    options = Options()
    options.headless = headless
    service = Service("/home/pi/geckodriver")
    # service = Service(r"C:\Users\xhico\OneDrive\Useful\geckodriver.exe")
    browser = webdriver.Firefox(service=service, options=options)
    type_tiny = pyshorteners.Shortener()

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
