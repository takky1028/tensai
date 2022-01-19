import discord
import random

TOKEN = 'Njk2Mjc1NTQ3NDQ1MTMzMzM0.XomXIg.yhz8hni-yYv7HR5Cf25S09DWPmQ'
TOKEN2 = 'ODQ0OTc4NzI3MTc0Nzk5Mzkw.YKaRww.NV53Alr1fqc_88mpVu7F0ckcZjo'
token_list = ["Njk2Mjc1NTQ3NDQ1MTMzMzM0.XomXIg.yhz8hni-yYv7HR5Cf25S09DWPmQ"
             ,"ODQ0OTc4NzI3MTc0Nzk5Mzkw.YKaRww.NV53Alr1fqc_88mpVu7F0ckcZjo"]

client = discord.Client()
client2 = discord.Client()

@client.event
async def on_ready():
    # 起動したらターミナルにログイン通知が表示される
    print('ログインしました')

# メッセージ受信時に動作する処理
@client.event
async def on_message(message):
    # メッセージ送信者がBotだった場合は無視する
    if message.author.bot:
        return
    # 「/neko」と発言したら「にゃーん」が返る処理
    if message.content == '/neko':
        await message.channel.send('にゃーん')


@client2.event
async def on_ready():
    # 起動したらターミナルにログイン通知が表示される
    print('ログインしました')

# メッセージ受信時に動作する処理
@client2.event
async def on_message(message):
    # メッセージ送信者がBotだった場合は無視する
    if message.author.bot:
        return
    # 「/neko」と発言したら「にゃーん」が返る処理
    if message.content == '/inu':
        await message.channel.send('わーん')

client.run(TOKEN)
client2.run(TOKEN2)
