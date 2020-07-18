from redbot.core import commands, Config, bank, checks
from redbot.core.data_manager import bundled_data_path

# You need to install pillow:
# pip install --upgrade Pillow
from PIL import Image, ImageDraw, ImageFont
import os
import discord


class PFPMaker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 88888888)
        default_guild = {
            "cost": 50000
        }
        self.config.register_guild(**default_guild)

    def profile_generator_4th_bday(self, name: str, text_color: str, outline: str):
        # Constants
        square_sz = 753
        path = str(bundled_data_path(self))

        # Images
        image = Image.new('RGBA', (square_sz, square_sz), color="white")
        logo = Image.open(path+'/non-transparent-hat.png')
        background = Image.open(path+'/bgtest.jpg')

        # Pasting Assets
        image.paste(background, (-120, 0))  # Background
        draw = ImageDraw.Draw(image)  # Draw Object
        if outline.lower() != 'none':
            for num in range(20):  # Circle Drawer
                draw.ellipse((num, num, square_sz - num, square_sz - num), outline=outline)
        image.paste(logo, (int((square_sz - 559) / 2), 10), logo)  # Legend Logo

        w, h, sz = 0, 0, 20

        # Text
        while w < 490 and h < 135:
            sz += 1
            font = ImageFont.truetype(path+"/Artbrush.ttf", size=sz)
            w, h = draw.textsize(name, font)
        draw.text(((square_sz - w) / 2, 540), name, fill=text_color, font=font)

        # Saving
        if not os.path.exists(path + "/4thBDayPFP/"):
            os.makedirs(path + "/4thBDayPFP/")
        image.save(path + "/4thBDayPFP/" + name + " Legend 4th Anniversary PFP.png")
        return path + "/4thBDayPFP/" + name + " Legend 4th Anniversary PFP.png"
        # print("File Saved at: \"" + name + " Legend 4th Anniversary PFP.png\"")

    @commands.command(name='4thbirthdaypfp')
    async def forthbirthdaypfp(self, ctx, text_color: str, border_color: str, * , name: str):
        """
        For text colors and border colors, all colors here are supported: https://en.wikipedia.org/wiki/X11_color_names
        **ENTER COLOR WITHOUT SPACES** -- If you wanted light blue for example, enter lightblue

        \nYou can enter "None" for border_color if you don't want a border

        Enter the name on the PFP without quotes after that. Note that on really long names it will be unreadable, try to keep it under 12 characters.
        
        Sample Command: `!4thbirthdaypfp lightgreen skyblue General Leoley`
        """
        path = self.profile_generator_4th_bday(name, text_color, border_color)
        await ctx.send("Done! Here's your PFP! *Profile Picture Generator Designed by Generaleoley*",
                       file=discord.File(path))
        os.remove(path)



