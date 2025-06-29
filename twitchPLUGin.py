#imports, requires twitchAPI and buttplug-py to be installed
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.chat import Chat, EventData, ChatMessage, ChatSub, ChatCommand
import asyncio
import logging
import sys
from buttplug import Client, WebsocketConnector, ProtocolSpec


#twitch parameters
#twitchSecret = ''
clientId = ''
token = ''
refreshToken = ''
userScope = [AuthScope.CHAT_READ]
targetChannel = 'paymoneywubby'
triggerPhrase = "KEKW"

#Device parameters - The key is the device name printed out from the device debug function.
#The data should be a dictionary containing "act": a count of the actuators on the device, then numbered lists starting from 0 for each actuator containing the intensity of each level
deviceParam = {
    "testScoring": {"act": 2, 0:[-1, 0, 0, 0.25, 0.5, 1], 1:[-1, 0.25, 0.45, 0.7, 1, 1]},
    "JoyHub Pearlconch":{"act": 2, 0:[-1, 0, 0, 0.25, 0.5, 1], 1:[-1, 0.25, 0.45, 0.7, 1, 1]}
}

#device websocket address - Defaults to ws://127.0.0.1:12345 to connect to a local server.  Can be changed to access a remote server.
wsAddress = "ws://127.0.0.1:12345"

#general parameters - Scoring defaults are intended to make each match add 1 second at level 1, down to adding 2/3rds a second at max level.
    #To tune scoring, the two primary things to change are:
    #score per match -  Best used to adjust for fast/slow chats.  Higher means longer activations and climbing levels quicker per match, better for slow chats; less is the opposite.
    #level min - Best used to adjust how quickly you want to climb levels without greatly impacting activation length.  Lowering amount between minimums causes levels to climb quicker; raising amount between minimums does the opposite.
    #secondary tuning can be done with score time step and level decay.  Score time step determines how often level decay occurs, while level decay determines how many points are removed from the score per time step.
#Instantiate the total score.  Default is 0.  Theoretically can start with a score to generate device activity from boot.
totalScore = 0
#Sets amount the score is increased for each chat message containing the trigger phrase  Default is 100. 
scorePerMatch = 100
#Sets the amount of time between level adjustment and scoring decay.  Default is 0.5
scoreTimeStep = 0.5
#Minimum score to advance level.  Level 0 is assumed to be off, so minimums start at level 1.  Setting the first value to 0 or less will cause device to constantly stay at level 1 or above.
#default values are [1, 500, 1000, 1500, 2000]
levelMin = [1, 500, 1000, 1500, 2000]
#The amount of score bled out per level for each score time step.  Currently level 0 is set to 0 as we reach level 1 at any value above 0.  If we adjust level 1's minimum above, this decay value will need to be changed.
#default values are [0, 50, 75, 100, 125, 150]
levelDecay = [0, 50, 75, 100, 125, 150]
quitScoringLoop = False
quitTwitchLoop = False

#Called once the bot is ready to join a channel to join the channel.  
async def onReady(ready_event: EventData):
    await ready_event.chat.join_room(targetChannel)

#Triggered on received messages from twitch chat.  Checks the text of the message for the trigger phrase, and if it is present increases the score by the amount set above.
async def onMessage(msg: ChatMessage):
    global totalScore
    if triggerPhrase in msg.text:
        totalScore += scorePerMatch

#Twitch chat module, closely following their example python code.
async def twitchChat():
    #make sure when we change our kill command boolean in another function it also changes here.
    global quitTwitchLoop
    
    #set up twitch api instance and add user authentication with some scopes
    #With the below commented out lines, we're not authenticating as an app.

    #use authenitcation
    #twitch = await Twitch(clientId, twitchSecret)
    #auth = UserAuthenticator(twitch, userScope)
    #token, refreshToken = await auth.authenticate()
        
    #bypass app authentication and authenticate user
    twitch = await Twitch(clientId, authenticate_app=False)
    await twitch.set_user_authentication(token, userScope, refreshToken)
    

    #create chat instance
    chat = await Chat(twitch)

    #register the handlers for the events you want
    chat.register_event(ChatEvent.READY, onReady)
    chat.register_event(ChatEvent.MESSAGE, onMessage)
    
    #start the chat instance
    chat.start()
    
    #loop of sleep statements to keep the function alive until we send the kill switch
    while not quitTwitchLoop:
        await asyncio.sleep(1)
    
    #stop chat and twitch instances
    chat.stop()
    await twitch.close()
    
#function to manually probe a connected device to confirm what functions do what.  Useful to add additional devices other than the one this was written for.  Requires killing python manually to exit.
async def deviceDebug(passedDevice):
    #checking to see if the device we connected to has any actuators we can control.  If not the device portion exits.
    if len(passedDevice.actuators) != 0:
        quitProg = 0
        
        #check if kill command has been given
        while quitProg != 1:
            print("Select a function.\n1) Quit\n2) Print Actuator Info\n3) Send test signal to device")
            actIndex = 0
            menuSelect = 0
            #make sure menu selection is valid, prompt for another selection if not.
            while menuSelect < 1 or menuSelect > int(len(passedDevice.actuators) + 2):
                menuSelect = 0
                while actIndex < len(passedDevice.actuators):
                    print(str(actIndex + 3) + ") " + passedDevice.actuators[actIndex].type)
                    actIndex += 1
                try:
                    menuSelect = int(input("Select: "))
                except:
                    print("Invalid Selection, try again.")
            
            #sends quit command
            if menuSelect == 1:
                quitProg = 1
            #prints off name of device and parameters of each actuator of the connected device
            elif menuSelect == 2:
                tempAct = 0
                print(passedDevice.name)
                while tempAct < len(passedDevice.actuators):
                    print("\nFunction " + str(tempAct+1))
                    print("Description: " + str(passedDevice.actuators[tempAct].description))        
                    print("Type: " + str(passedDevice.actuators[tempAct].type))        
                    print("Index: " + str(passedDevice.actuators[tempAct].index))        
                    print("Step Count: " + str(passedDevice.actuators[tempAct].step_count))
                    tempAct += 1
            #gathers the actuator, intensity, and length of test signal, then sends the command to the device
            else:
                actIndex = menuSelect - 3
                
                intensity = -1
                while intensity < 0 or menuSelect > int(passedDevice.actuators[actIndex].step_count):
                    intensity = -1
                    try:
                        intensity = int(input("Available Range: " + str(passedDevice.actuators[actIndex].index) + "-" + str(passedDevice.actuators[actIndex].step_count) + "\nEnter Intensity: "))
                    except:
                        print("Invalid Selection")
                
                length = int(input("Enter Length in Seconds: "))
                
                await passedDevice.actuators[actIndex].command(float(intensity)/float(passedDevice.actuators[actIndex].step_count))
                await asyncio.sleep(length)
                await passedDevice.actuators[actIndex].command(-1)

#Function to set device/decay level, either set actuator level on device or print score, wait at that level for the score time step, then decay the score based on the set level.
async def scoring(passedDevice = None):
    global totalScore
    global quitScoringLoop
    #set device parameters
    if passedDevice  != None:
        connectedDeviceParam = deviceParam[passedDevice.name]
    else:
        connectedDeviceParam = deviceParam["testScoring"]
        
    #decay/level select logic
    while not quitScoringLoop:
        levelSelect = 0
        while totalScore >= levelMin[levelSelect]:
            levelSelect += 1
            if levelSelect >= (len(connectedDeviceParam[0])):
                break
        
        #Twitch scoring debug, prints score as opposed to controls a device.
        if passedDevice == None:
            print(totalScore)
        #If the debug device wasn't sent, sets intensity of actuators on connected device.
        else:
            #Set the intensity of the device based on the level derived from the scoring logic above.
            actSelect = 0
            while actSelect < connectedDeviceParam["act"]:
                await passedDevice.actuators[actSelect].command(connectedDeviceParam[actSelect][levelSelect])
                actSelect += 1
        
        #sleep for the cycle time set above
        await asyncio.sleep(scoreTimeStep)
        
        #decay
        if totalScore <= levelDecay[levelSelect]:
            totalScore = 0
        else:
            totalScore -= levelDecay[levelSelect]

#Main device function closely following the buttplug-py project's example code.  This initializes the device if a main menu option is selected that would otherwise require a device connection
async def device():
    client = Client("twitchPLUGin", ProtocolSpec.v3)
    connector = WebsocketConnector(wsAddress, logger=client.logger)
    try:
        await client.connect(connector)
    except Exception as e:
        logging.error(f"Could not connect to server, exiting: {e}")
        return

    #Now we move on to looking for devices. We will tell the server to start scanning for devices. It returns while it is scanning, so we will wait for 10 seconds, and then we will tell the server to stop scanning.
    await client.start_scanning()
    await asyncio.sleep(10)
    await client.stop_scanning()

    #If we selected the live option in the main menu, we start scoring.  If we otherwise selected to debug a device, we start that function.
    if len(client.devices) != 0:
        connectedDevice = client.devices[0]
        if int(mainMenu) == 1:
            await scoring(connectedDevice)
        elif int(mainMenu) == 2:
            await deviceDebug(connectedDevice)
    
    #Disconnect device once we exit the above called function
    await client.disconnect()


#Way to escape the twitch/device loops once started.  The loops check to see if a quit command was given here.  If the stop command is detected, it sets the quit command was given which causes the loops to gracefully exit.
async def exitLoop():
    global quitScoringLoop
    global quitTwitchLoop
    stopCommand = ""
    while stopCommand != "STOP":
        try:
            stopCommand = await asyncio.to_thread(input, "Send \"STOP\" to quit program\n")
        except:
            stopCommand = ""
        
    quitScoringLoop = True
    quitTwitchLoop = True

#Launcher for main functions.  Runs functions based on main menu selection.
async def main():
    #runs twitch, device, and the exit functions for full functionality
    if mainMenu == 1:
        await asyncio.gather(asyncio.create_task(device()), asyncio.create_task(twitchChat()), exitLoop())
    #runs solely the device in debug mode to test/develop for a device
    elif mainMenu == 2:
        await asyncio.gather(asyncio.create_task(device()))
    #runs solely the twitch chat bot and scoring function to fine tune scores/make sure phrase detection is working as expected
    else:
        await asyncio.gather(asyncio.create_task(twitchChat()), asyncio.create_task(scoring()))

#Allows you to set the chat channel to monitor, as well as the trigger word/phrase that the chat message must contain to add to the score
targetChannel = input("Chat Channel Name: ")
triggerPhrase = input("Trigger Phrase: ")

mainMenu = 0
while mainMenu < 1 or mainMenu > 3:
    try:
        mainMenu = int(input("Program Mode:\n1) Live\n2) Debug Device\n3) Debug Twitch\nSelect: "))
    except:
        print("Invalid input, please try again.")

asyncio.run(main())