# -*- coding: utf-8 -*-
# !/usr/bin/python3

# python3 -m pip install yagmail tweepy selenium pdf2image psutil --no-cache-dir
# sudo apt install poppler-utils -y

import json
import os
import datetime
import shutil
import urllib.request
import tweepy
import yagmail
import pdf2image
import psutil
import traceback
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from Misc import get911


def getLastTweetedPost():
    """
    Retrieves the date, title, and href of the last tweeted post from the CONFIG_FILE.

    Returns:
    - A tuple containing the date (string), title (string), and href (string) of the last tweeted post.
      If there is no last tweeted post, an empty string is returned for each element of the tuple.
    """
    try:
        # Open the CONFIG_FILE and load its contents into a dictionary.
        with open(CONFIG_FILE) as inFile:
            data = json.load(inFile)[0]
        # Return the date, title, and href of the last tweeted post from the dictionary.
        return data["date"], data["title"], data["href"]
    except Exception:
        # If there is an exception (e.g. the CONFIG_FILE is empty or doesn't exist), return empty strings.
        return "", "", ""


def getPosts():
    """
    This function retrieves a list of new posts from a website by comparing the latest post on the website
    with the latest post that has been tweeted.

    Returns:
        list: A list of dictionaries containing the date, title, and href for each new post.
    """

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
        logger.info("Reverse Documents")
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
    """
    Downloads a PDF file from a given URL, converts its first four pages into JPEG images, and saves them in a temporary
    folder.

    Args:
        pdfHref (str): The URL of the PDF file to be downloaded and converted.

    Returns:
        bool: True if the PDF file was successfully downloaded and at least one screenshot was saved, False otherwise.
    """
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
            # If running on Windows, set the path to the Poppler binary
            poppler_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "poppler-win\Library\bin")
            # Convert the PDF pages to images using Poppler
            pages = pdf2image.convert_from_path(poppler_path=poppler_path, pdf_path=pdfFile)
        else:
            # If running on a different OS, use the default PDF converter
            pages = pdf2image.convert_from_path(pdf_path=pdfFile)

        # Save the first four pages as JPEG images
        for idx, page in enumerate(pages[0:4]):
            jpgFile = os.path.join(tmpFolder, "tmp_" + str(idx) + ".jpg")
            page.save(jpgFile)
        hasPics = True
    except Exception:
        # If any error occurs during the process, log it and set hasPics to False
        logger.error("Failed to screenshot")
        hasPics = False

    return hasPics


def tweet(tweetStr):
    """
    Tweets a message and any images in the specified folder.

    Args:
        tweetStr: The message to tweet.
    """
    try:
        # Find all JPG files in the specified folder and sort them.
        imageFiles = sorted([os.path.join(tmpFolder, file) for file in os.listdir(tmpFolder) if file.split(".")[-1] == "jpg"])

        # Upload each image to Twitter and get its media ID.
        media_ids = [api.media_upload(os.path.join(tmpFolder, image)).media_id_string for image in imageFiles]

        # Tweet the message along with any attached images.
        api.update_status(status=tweetStr, media_ids=media_ids)
        logger.info("Tweeted")
    except TweepError as ex:
        # If an error occurs while tweeting, log the error and send an email to the specified recipient.
        logger.error("Failed to Tweet")
        yagmail.SMTP(EMAIL_USER, EMAIL_APPPW).send(EMAIL_RECEIVER, "Failed to Tweet - " + os.path.basename(__file__), str(ex) + "\n\n" + tweetStr)


def batchDelete():
    """
    Deletes all tweets from the authenticated user's Twitter account using the Tweepy library and the
    Twitter API. The function first logs the start of the tweet deletion process, then retrieves all the
    user's tweets using the Tweepy Cursor object and the user_timeline endpoint. It then loops through
    each tweet and deletes it using the destroy_status method of the Tweepy API. If any errors occur
    during the tweet deletion process, the function will suppress them and continue processing the
    remaining tweets.
    """
    logger.info("Deleting all tweets from the account @" + api.verify_credentials().screen_name)
    # Retrieve all tweets from the authenticated user's timeline using the Tweepy Cursor object and the user_timeline endpoint.
    for status in tweepy.Cursor(api.user_timeline).items():
        try:
            # Delete each tweet using the destroy_status method of the Tweepy API.
            api.destroy_status(status.id)
        except Exception:
            # If an error occurs during tweet deletion, suppress the error and continue processing the remaining tweets.
            pass


def main():
    """
    A function to get the latest posts from a website, take a screenshot of their PDFs and tweet about them with hashtags.

    Returns:
    None
    """

    # Get latest posts
    logger.info("Get latest posts")
    newPosts = list(reversed(getPosts()))  # Get latest posts and reverse the order.

    # Set hashtags
    hashtags = "#FIM #FIMfamily #GrandPrix #MotoGP"

    # Go through each new post
    for post in newPosts:
        # Get post info
        postTitle, postDate, postHref = post["title"], post["date"], post["href"]
        logger.info(postTitle)
        logger.info(postDate)

        # Get PDF link
        try:
            browser.get(postHref)
            pdfHref = browser.find_element(By.CLASS_NAME, "news-infos").find_element(By.TAG_NAME, "a").get_attribute("href")
            pdfHref = "".join(pdfHref.split("?t=")[:-1])

            # Screenshot DPF
            getScreenshots(pdfHref)
        except Exception:
            pdfHref = postHref

        # Tweet!
        tweet(postTitle + "\n\n" + "Published at: " + postDate + "\n\n" + pdfHref + "\n\n" + hashtags)

        # Save log
        if not os.path.exists(CONFIG_FILE):
            # If the config file doesn't exist, create an empty list and write to the file.
            with open(CONFIG_FILE, "w") as outFile:
                json.dump(list(reversed({})), outFile, indent=2)
        with open(CONFIG_FILE) as inFile:
            # Load the data from the config file, reverse the order and add the latest post to the list.
            data = list(reversed(json.load(inFile)))
            data.append(post)
        with open(CONFIG_FILE, "w") as outFile:
            # Write the updated list to the config file, reversing the order again.
            json.dump(list(reversed(data)), outFile, indent=2)


if __name__ == "__main__":
    # Set Logging
    LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.path.abspath(__file__).replace(".py", ".log"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
    logger = logging.getLogger()

    logger.info("----------------------------------------------------")

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

    # Set temp folder
    tmpFolder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp")
    CONFIG_FILE = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"))

    # Check if script is already running
    procs = [proc for proc in psutil.process_iter(attrs=["cmdline"]) if os.path.basename(__file__) in '\t'.join(proc.info["cmdline"])]
    if len(procs) > 2:
        logger.info("isRunning")
    else:
        headless = True
        options = Options()
        options.headless = headless
        service = Service("/home/pi/geckodriver")
        # service = Service(r"C:\Users\xhico\OneDrive\Useful\geckodriver.exe")
        browser = webdriver.Firefox(service=service, options=options)

        try:
            main()
        except Exception as ex:
            logger.error(traceback.format_exc())
            yagmail.SMTP(EMAIL_USER, EMAIL_APPPW).send(EMAIL_RECEIVER, "Error - " + os.path.basename(__file__), str(traceback.format_exc()))
        finally:
            if headless:
                browser.close()
                logger.info("Close")
            logger.info("End")
