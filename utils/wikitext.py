def insert_iaparams_to_wikitext(iaparams: str, wikitext: str):
    """find the end of {{Website template in wikitext, and insert params"""

    if wikitext.count("{{Website") > 1:
        print('Warning: multiple {{Website}} templates found, please check manually. skippping...')
        return None

    start = wikitext.find("{{Website")
    end = None
    count = 0
    for i in range(start, len(wikitext)):
        if wikitext[i] == "{":
            count += 1
        elif wikitext[i] == "}":
            count -= 1
            if count == 0:
                end = i
                break

    if end is None:
        print('Warning: no matching "}}" found, please check manually. skippping...')
        return None

    target = end - 2
    
    # insert params to the end of {{Website template
    return wikitext[:target] + "\n" + iaparams + wikitext[target:]