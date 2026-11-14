-- glosses: machine translation into English of the quoted sentences
SELECT lang, h, text_en FROM gloss WHERE h IN %(hs)s
