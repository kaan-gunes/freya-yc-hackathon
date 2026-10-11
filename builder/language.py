"""Portable input grammar; business calendar and limits remain in the workflow."""


def normalize_amount_input(raw):
    import re
    text = str(raw or '').lower().replace('’', "'").strip()
    text = re.sub(r"\s*(?:tl|try|türk lirası|turk lirasi|lira)(?:'?(?:yi|yı|i|ı))?$", '', text).strip()
    if text != str(raw or '').strip().lower() and re.fullmatch(r'[+-]?[0-9]{1,3}(?:\.[0-9]{3})+', text):
        return text.replace('.', '')
    if re.fullmatch(r'[+-]?[0-9]{1,3}(?:\.[0-9]{3})+,[0-9]{1,2}', text):
        return text.replace('.', '').replace(',', '.')
    if re.fullmatch(r'[+-]?[0-9]+,[0-9]{1,2}', text):
        return text.replace(',', '.')
    if text != str(raw or '').strip().lower() and re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?', text):
        return text
    return str(raw or '')


def normalize_date_input(raw, anchor='', deadline='', identity=False):
    import datetime
    import re
    text = str(raw or '').lower().replace('’', "'").replace('i̇', 'i')
    text = text.translate(str.maketrans('çğıöşü', 'cgiosu')).strip(' \t\r\n.,!?;:')
    text = re.sub(r'\s+', ' ', text)
    if identity:
        text = re.sub(r'^(?:benim )?(?:dogum tarihim|dogum tarihimdir|dogum tarihim su|date of birth is|my date of birth is)\s*[:=]?\s*', '', text)
    text = re.sub(r"(?:'?(?:de|da|te|ta)| tarihinde| gunu)$", '', text).strip()
    months = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']
    turkish_months = ['ocak', 'subat', 'mart', 'nisan', 'mayis', 'haziran', 'temmuz', 'agustos', 'eylul', 'ekim', 'kasim', 'aralik']
    weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    turkish_weekdays = ['pazartesi', 'sali', 'carsamba', 'persembe', 'cuma', 'cumartesi', 'pazar']
    small = dict(zip(['bir', 'iki', 'uc', 'dort', 'bes', 'alti', 'yedi', 'sekiz', 'dokuz', 'on', 'on bir', 'on iki', 'on uc', 'on dort', 'on bes', 'on alti', 'on yedi', 'on sekiz', 'on dokuz', 'yirmi', 'yirmi bir', 'yirmi iki', 'yirmi uc', 'yirmi dort', 'yirmi bes', 'yirmi alti', 'yirmi yedi', 'yirmi sekiz', 'yirmi dokuz', 'otuz', 'otuz bir'], range(1, 32)))
    english = ['one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty', 'twenty one', 'twenty two', 'twenty three', 'twenty four', 'twenty five', 'twenty six', 'twenty seven', 'twenty eight', 'twenty nine', 'thirty', 'thirty one']
    ordinals = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth', 'tenth', 'eleventh', 'twelfth', 'thirteenth', 'fourteenth', 'fifteenth', 'sixteenth', 'seventeenth', 'eighteenth', 'nineteenth', 'twentieth', 'twenty first', 'twenty second', 'twenty third', 'twenty fourth', 'twenty fifth', 'twenty sixth', 'twenty seventh', 'twenty eighth', 'twenty ninth', 'thirtieth', 'thirty first']
    days = dict(zip(english + ordinals, list(range(1, 32)) * 2))
    days.update(small)
    def day_number(value):
        value = re.sub(r'(?<=[0-9])(?:st|nd|rd|th)$', '', value.strip())
        return int(value) if re.fullmatch(r'[0-9]{1,2}', value) else days.get(value)
    try:
        if re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', text):
            return datetime.date.fromisoformat(text).isoformat()
        match = re.fullmatch(r'([0-9]{1,2})[/.\-]([0-9]{1,2})[/.\-]([0-9]{4})', text)
        if match:
            return datetime.date(int(match.group(3)), int(match.group(2)), int(match.group(1))).isoformat()
        start = datetime.date.fromisoformat(str(anchor)[:10]) if anchor else None
        end = datetime.date.fromisoformat(str(deadline)[:10]) if deadline else None
        if not identity and start and text in ('today', 'bugun', 'tomorrow', 'yarin'):
            return (start + datetime.timedelta(days=1 if text in ('tomorrow', 'yarin') else 0)).isoformat()
        names = months + turkish_months
        clean = text.replace(',', ' ').replace('-', ' ')
        clean = re.sub(r'\s+', ' ', clean).strip()
        first = re.fullmatch(r'(?:the )?(.+?) (?:of )?(' + '|'.join(names) + r')(?: ([0-9]{4}))?', clean)
        last = re.fullmatch(r'(' + '|'.join(names) + r') (?:the )?(.+?)(?: ([0-9]{4}))?', clean)
        if first or last:
            match = first or last
            day = day_number(match.group(1) if first else match.group(2))
            month_name = match.group(2) if first else match.group(1)
            month = names.index(month_name) % 12 + 1
            year = match.group(3)
            if day is None or not 1 <= day <= 31 or (identity and not year):
                return ''
            if year:
                return datetime.date(int(year), month, day).isoformat()
            # shortcut: a missing sourced date range stays yearless for the existing policy parser.
            if not start or not end:
                datetime.date(2000, month, day)
                return str(day) + ' ' + months[month - 1]
            if end < start or end.year - start.year > 20:
                return ''
            matches = []
            for year_value in range(start.year, end.year + 1):
                try:
                    date = datetime.date(year_value, month, day)
                except ValueError:
                    continue
                if start <= date <= end:
                    matches.append(date)
            return matches[0].isoformat() if len(matches) == 1 else ''
        if not identity and start:
            match = re.fullmatch(r'(?:(this|next|bu|gelecek|onumuzdeki) )?(' + '|'.join(weekdays + turkish_weekdays) + r')(?: (?:the )?(.+))?', clean)
            if match:
                weekday = (weekdays + turkish_weekdays).index(match.group(2)) % 7
                if match.group(3):
                    day = day_number(match.group(3))
                    if day is None or not end or end < start or (end - start).days > 366:
                        return ''
                    dates = [start + datetime.timedelta(days=offset) for offset in range((end - start).days + 1)]
                    matches = [date for date in dates if date.day == day and date.weekday() == weekday]
                    return matches[0].isoformat() if len(matches) == 1 else ''
                qualifier = match.group(1)
                if qualifier:
                    date = start - datetime.timedelta(days=start.weekday()) + datetime.timedelta(days=weekday + (7 if qualifier in ('next', 'gelecek', 'onumuzdeki') else 0))
                    return date.isoformat()
                if end and 0 <= (end - start).days <= 366:
                    dates = [start + datetime.timedelta(days=offset) for offset in range((end - start).days + 1)]
                    matches = [date for date in dates if date.weekday() == weekday]
                    return matches[0].isoformat() if len(matches) == 1 else ''
        return ''
    except (ValueError, TypeError, OverflowError):
        return ''
