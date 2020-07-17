from PIL import Image, ImageDraw, ImageFont


#  File name: <Username> Legend 4th Anniversary PFP

def profile_generator(name: str, text_color: str, outline: str):
    # Constants
    square_sz = 753

    # Images
    image = Image.new('RGBA', (square_sz, square_sz), color="white")
    logo = Image.open('non-transparent-hat.png')
    background = Image.open('bgtest.jpg')

    # Pasting Assets
    image.paste(background, (-120, 0))  # Background
    draw = ImageDraw.Draw(image)  # Draw Object
    for num in range(6):  # Circle Drawer
        draw.ellipse((num, num, square_sz - num, square_sz - num), outline=outline)
    image.paste(logo, (int((square_sz - 559) / 2), 3), logo)  # Legend Logo

    w, h, sz = 0, 0, 20

    # Text
    while w < 490 and h < 135:
        sz += 1
        font = ImageFont.truetype("Artbrush.ttf", size=sz)
        w, h = draw.textsize(name, font)
    draw.text(((square_sz - w) / 2, 540), name, fill=text_color, font=font)

    # Saving
    image.save(name + " Legend 4th Anniversary PFP.png")
    print("File Saved at: \"" + name + " Legend 4th Anniversary PFP.png\"")


# User-interface, I'm not error catching for colors so just be wary of that

name = input("Username: ")
text_color = input("Text Color: ")
border_color = input("Border Color: ")
profile_generator(name, text_color, border_color)