s = ""
for (i = 0; i < card_yellows.length; i++) {
    item = card_yellows[i]

    an = item.querySelector('.content')
    if (an == null) continue
    a2 = an.querySelector('.ui, .header')
    name = a2.text
    names = name.split('\n')
    name = names[2]
    tag = a2.href
    tags = tag.split('/')
    tag = tags[tags.length - 1]
    s += (`"${name}": "${tag}",\n`)
}
console.log(s)
