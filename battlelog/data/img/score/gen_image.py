from PIL import Image, ImageDraw, ImageFont

# generate all possible scores
scores = []
for i in range(10):
    for j in range(10):
        scores.append(f"{i}-{j}")
score = scores[0]
crown_y_offset = 20
red_crown_x_offset = 505
font_color = (255, 255, 255, 128)

font_file_regular = "../../fonts/OpenSans-Regular.ttf"
font_size = 180
font_regular = ImageFont.truetype(font_file_regular, size=font_size)
image_original = Image.open("../double_size_no_logo.png")
image_original = image_original.resize((750, 200 + crown_y_offset,))

blue_crown = Image.open("crown-blue.png")
blue_crown = blue_crown.resize((blue_crown.width * 2, blue_crown.height * 2,))
red_crown = Image.open("crown-red.png")
red_crown = red_crown.resize((red_crown.width * 2, red_crown.height * 2,))

for score in scores:
    image = image_original.copy()
    image.paste(blue_crown, (0, crown_y_offset,))

    txt = Image.new("RGBA", image.size, (255, 255, 255, 0))
    d = ImageDraw.Draw(txt)
    d.text((blue_crown.width, 0), score, font=font_regular, fill=font_color)
    image = Image.alpha_composite(image, txt)

    image.paste(red_crown, (red_crown_x_offset, crown_y_offset,))

    # image.show()
    image.save(f"{score}.png")
    image.close()
    # print("Completed", score)
