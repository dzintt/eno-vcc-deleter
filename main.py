import json, ctypes, asyncio, logging, sys
from pyppeteer import launch

#stfu
logging.disable(logging.CRITICAL)

#class that deletes Capital 1 Eno VCC's
class DeleteVCC:
    #constructor
    def __init__(self, username, password, search):
        self.deleted = 0
        self.search = search
        self.user = username
        self.pw = password
        asyncio.run(self.initBrowser())

    #function to prepare a browser with important steps such as login required for the rest of the program to function properly
    async def initBrowser(self):

        #create main browser object
        self.browser = await launch({'headless': False , 'defaultViewport': None}, handleSIGINT=False, handleSIGTERM=False, handleSIGHUP=False, logLevel=0, autoClose=False)
        page = await self.browser.pages()
        page = page[0]

        #intercept requests to retrieve important data
        await page.setRequestInterception(True)
        page.on('request', lambda req: asyncio.ensure_future(interceptReq(req)))
        page.on('response', lambda resp: asyncio.ensure_future(interceptResp(resp)))

        #login
        await page.goto("https://verified.capitalone.com/auth/signin", {'waitUntil':'networkidle2'})
        await sendKeys(page, '//*[@id="ods-input-0"]', self.user, 10000)
        await sendKeys(page, '//*[@id="ods-input-1"]', self.pw, 10000)
        await click(page, '//*[@type="submit"]', 10000)

        #check for successful login
        url = await page.evaluate("window.location.href")
        while not url.startswith("https://myaccounts.capitalone.com/accountSummary"):
            await page.waitForNavigation({'waitUntil':'load', 'timeout': 0})
            url = await page.evaluate("window.location.href")

        #get VCC data
        await page.goto("https://myaccounts.capitalone.com/VirtualCards", {'waitUntil':'networkidle0'})

        #add data to the queue for the workers tasks later
        queue = asyncio.Queue()
        self.totalVCC = 0
        for card in cardData.keys():
            for e in cardData[card]["entries"]:
                if e["tokenName"] == self.search:
                    await queue.put(f"{card}:{e['tokenReferenceId']}")
                    self.totalVCC += 1

        print(f"Found {len(cardData.items())} Cards and a Total of {self.totalVCC} VCC's matching '{self.search}'")
        ctypes.windll.kernel32.SetConsoleTitleW(f"Capital One VCC Deleter ~ By @dzintt | Progress: {self.deleted}/{self.totalVCC}")

        #stop intercepting requests since all data has already been retrieved
        await page.setRequestInterception(False)
        
        #create worker tasks
        tasks = []
        for i in range(taskAmount):
            tasks.append(asyncio.create_task(self.delete(queue, taskName=f"Task {i+1}")))
        await queue.join()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    #worker function that handles vcc deletion
    async def delete(self, queue, taskName):
        while True:
            isEmpty = queue.empty()
            if not isEmpty:
                #get queue data
                data = await queue.get()
                print(f"[{taskName}] Starting Delete")
                cardRef, vccToken = data.split(":")

                #create a new tab for every task to maximize efficiency
                taskPage = await self.browser.newPage()
                await taskPage.goto(f"https://myaccounts.capitalone.com/VirtualCards/editVirtualCard?tokenRef={vccToken}&cardRef={cardRef}&reveal=false", {'waitUntil':'networkidle0'})
                print(f"[{taskName}] Deleting Card...")
                await asyncio.sleep(1)

                #click delete buttons
                await taskPage.evaluate('document.getElementsByClassName("deleteLink vc-delete-button c1-ease-button--full-width c1-ease-button c1-ease-button--progressive c1-ease-button--text")[0].click()')
                await asyncio.sleep(0.25)
                await taskPage.evaluate('document.getElementsByClassName("deleteButton c1-ease-button--full-width c1-ease-button c1-ease-button--destructive")[0].click()')

                await asyncio.sleep(2)

                self.deleted += 1
                ctypes.windll.kernel32.SetConsoleTitleW(f"Capital One VCC Deleter ~ By @dzintt | Progress: {self.deleted}/{self.totalVCC}")

                #clean up
                await taskPage.close()
                print(f"[{taskName}] Card Deleted")
            else:
                break

        print(f"[{taskName}] Task Finished")
        await queue.task_done()

#function to easily click
async def click(page, xpath, time):
    page.waitForXPath(xpath, timeout=time)
    result = await page.Jx(xpath)
    await result[0].click()

#function to easily send input
async def sendKeys(page, xpath, text, time):
    page.waitForXPath(xpath, timeout=time)
    result = await page.Jx(xpath)
    await result[0].type(text)

#function to allow requests to continue since we are intercepting
async def interceptReq(req):
    await req.continue_()

#function to catch responses and evaluate them
async def interceptResp(resp):
    global cardData

    #get VCC data by checking if the response URL is the endpoint for card data
    if resp.url.startswith("https://myaccounts.capitalone.com/ease-app-web/customer/virtualcards/tokens?cardReferenceId="):

        #parse the data and store it in a dict called cardData
        cardRefId = resp.url.split("cardReferenceId=")[1]
        data = await resp.json()
        if data["entries"]:
            cardData[cardRefId] = data

#function to get settings and store in variables
def getSettings():
    global username, password, cardData, taskAmount
    settings = json.load(open("./settings.json"))
    username = settings["username"]
    password = settings["password"]
    taskAmount = settings["tasks"]
    cardData = {}

#main
def main():
    ctypes.windll.kernel32.SetConsoleTitleW(f"Capital One VCC Deleter ~ By @dzintt | Progress: N/A")
    search = input("Card Names to Delete: ")
    getSettings()
    DeleteVCC(username, password, search)
    input("Completed. Press ENTER to exit.")
    sys.exit()
        
if __name__ == '__main__':
    main()