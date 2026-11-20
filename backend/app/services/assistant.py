import os
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from .knowledge import published_rows, today
from .rag_service import keyword_search, normalize
from .retrieval import retrieve_knowledge
from .llm_service import claims_completed_transaction, format_borrowing_guide, generate_answer, provider_name, MAX_MODEL_MESSAGE_CHARS
from .catalog import contextual_question,is_book_request,is_borrowing_procedure,search_guidance,unquoted_text,book_query,search_books,book_attribute,book_followup,selected_title,author_query,structured_book_query,PENALTY_WORD
from .catalog import direct_document_question, explicit_metadata_lookups, search_books_with_status, book_position, book_reference, public_book, normalize_catalog, book_attributes, search_correction
from .catalog import edited_book_year_question, question_clause_ends, book_format_filter
from urllib.parse import urlencode
from .opac_availability import get_availability
from .recommendations import is_recommendation_request, recommend_books

SUGGESTIONS = ['Hướng dẫn tra cứu OPAC','Thư viện mở cửa lúc mấy giờ hôm nay?','Tôi muốn gia hạn sách']
CATALOG_SEARCH_EXAMPLES = (
    ('Nhan đề', 'Tìm theo nhan đề 10 năm Olympic cơ học'),
    ('Tác giả', 'Tìm theo tác giả Đào Huy Bích'),
    ('Chủ đề', 'Tìm sách về Olympic cơ học'),
)
HOURS_INTENT = re.compile(r'\b(mo cua|dong cua|lich phuc vu|gio phuc vu|thoi gian phuc vu|mo tu may gio|mo may gio|may gio mo|dong may gio|mo den may gio)\b')
HOURS_SOURCE = {
    'title': 'LIC UTH — Hướng dẫn sử dụng thư viện, trang 12',
    'url': 'https://lic.ut.edu.vn/wp-content/uploads/2024/11/1.HD-su-dung-thu-vien-va-khai-thac-hieu-qua-cac-CSDL-tai-nguyen-thong-tin-thu-vien.pdf#page=12',
    'checked_at': '2026-11-12',
}
WEEKDAY_LABELS = ('Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ nhật')
WEEKDAY_HOURS = ('07:30–18:30',) * 5 + ('08:30–16:30', 'nghỉ phục vụ')
LIBRARY_CAMPUSES = ('1','2','3')
DAY_OFFSETS = {'hom nay': 0, 'bay gio': 0, 'luc nay': 0, 'mai': 1, 'ngay mai': 1, 'ngay mot': 2, 'ngay kia': 2}
HOURS_DAY = r'thu (?:hai|ba|tu|nam|sau|bay|[2-7])|chu nhat'
HOURS_FOLLOWUP = re.compile(r'(?:(?:con|vay|the) )?(?:'+HOURS_DAY+r'|hom nay|(?:ngay )?mai)(?: thi sao| a)?')
LIBRARY_CAMPUS_NAMES = {'1':'thanh my tay|binh thanh|vo oanh','2':'an khanh|thu duc','3':'trung my tay|quan 12|to ky'}
HOURS_CLOCK = (r'(?:luc|vao) (\d{1,2})\s*(?:h|gio)(?:\s*(\d{2})(?: phut)?)?\b'
               r'(?: (?:buoi )?(sang|trua|chieu|toi|am|pm))?\b')
HOURS_TIME_FOLLOWUP = re.compile(r'(?:(?:con|vay|the) )?'+HOURS_CLOCK+r'(?: thi sao| khong)?(?: a)?')
DISPLAYED_SCHEDULE = re.compile(
    r'^(?:lich phuc vu )?(?P<weekday>'+HOURS_DAY+r')'
    r'(?: (?P<date>\d{2} \d{2} \d{4}))?(?: (?:luc )?(?P<hour>\d{2})h(?P<minute>\d{2}))?'
    r' (?:lich chung|thu vien uth|nam (?:trong khung|ngoai) gio phuc vu|tai |co so )')
HOURS_CAMPUS_FOLLOWUP = re.compile(
    r'(?:(?:con|vay|the) )?(?:o )?(?:(?:co so|cs)\s*[123]|'+
    '|'.join(LIBRARY_CAMPUS_NAMES.values())+r')(?: '+HOURS_CLOCK+r')?(?: thi sao| khong)?(?: a)?')
HOURS_NOW = r'(?:con|dang) mo(?: cua)?'
GROUP_ROOM = re.compile(r'\b(?:phong hoc nhom|phong doc nhom|hoc nhom)\b')
LUNCH_HOURS = re.compile(r'\b(?:nghi trua|xuyen trua|thong trua|mo cua buoi trua|mo buoi trua)\b')
COURTESY = ('cam on','cam on ban','thank you','thanks','ok')

# Imported FAQ text can predate the current presentation of citations.
FAQ_OPENINGS = (
    ('Theo trang Phục vụ mượn–trả tài liệu, bạn đọc xuất trình thẻ, tra tìm tài liệu bằng máy tính hoặc trong kho, dùng sơ đồ và bảng chỉ dẫn kệ để xác định tài liệu, rồi mang sách ra quầy thủ thư làm thủ tục ghi mượn.',
     'Mang thẻ bạn đọc và xuất trình khi làm thủ tục mượn. Tìm sách bằng máy tính hoặc trong kho. Dùng sơ đồ kho và bảng chỉ dẫn kệ để tìm đúng cuốn, rồi mang sách đến quầy thủ thư để ghi mượn.'),
    ('Theo trang Phục vụ phòng đọc của LIC, bạn đọc xuất trình', 'Xuất trình'),
    ('Trang Sử dụng máy tính & Internet hướng dẫn xuất trình', 'Xuất trình'),
    ('Trang Hỗ trợ nhanh của LIC công bố email', 'Bạn có thể liên hệ qua email'),
    ('Trang Hướng dẫn sử dụng tài nguyên thư viện tập hợp các hướng dẫn cho', 'Bạn có thể xem hướng dẫn sử dụng'),
    ('Trang Xuất bản, phát hành tài liệu của LIC giới thiệu việc', 'Thư viện hỗ trợ'),
    ('Trang Học tập cá nhân, học nhóm của LIC hiện chỉ có nội dung chờ cập nhật, chưa cung cấp quy trình đặt phòng hoặc lịch trống.',
     'Mình chưa có quy trình đặt phòng học nhóm hoặc lịch phòng trống.'),
    ('Theo mục Thư viện các cơ sở và phần địa chỉ trên trang chủ LIC:', 'Bạn có thể đến thư viện tại ba cơ sở sau.'),
)


def source(row):
    return {'title':row['source_title'], 'url':row['source_url'], 'checked_at':row['checked_at']}


def result(answer,status='answered',sources=None,suggestions=None,mode='faq'):
    references=[]
    for citation in sources or []:
        if citation not in references:
            references.append(citation)
    if references and mode in ('faq','rag','fallback'):
        paragraphs = answer.split('\n\n')
        for index, paragraph in enumerate(paragraphs):
            for prefix, replacement in FAQ_OPENINGS:
                if paragraph.startswith(prefix):
                    paragraphs[index] = replacement + paragraph[len(prefix):]
                    break
        answer = '\n\n'.join(paragraphs)
    return {'answer':answer,'status':status,'sources':references,'suggestions':suggestions or [],'mode':mode}


def asks_library_hours(q):
    return (HOURS_INTENT.search(q) or (LUNCH_HOURS.search(q) and re.search(r'\b(?:thu vien|(?:co so|cs)\s*[123])\b',q))
            or (re.search(r'\b(?:thu vien|(?:co so|cs)\s*[123])\b',q) and
                re.search(r'\bmo (?:(?:luc|vao|tu|den) \d{1,2}|(?:hom nay|ngay mai)\b)',q))
            or ('thu vien' in q and re.search(
                r'\b(?:co mo|'+HOURS_NOW+r'|co lam viec|co phuc vu|gio lam viec|co nghi|nghi khong|(?:mo|dong) (?:luc|tu|den) may gio)\b',q)))


def campus_hours(default, overrides=None, campuses=LIBRARY_CAMPUSES):
    overrides = overrides or {}
    return '\n'.join(f'Cơ sở {campus} — {overrides.get(campus,default)}' for campus in campuses)


def clock_service(clock, windows):
    for opens,closes in re.findall(r'(\d{2}:\d{2})–(\d{2}:\d{2})',windows):
        if opens<=clock<closes:
            return 'trong khung giờ phục vụ'
    return 'ngoài giờ phục vụ'


def requested_campuses(query):
    branches = set(re.findall(r'\b(?:co so|cs)\s*(\d+)\b',query))
    for match in re.finditer(r'\b(?:co so|cs)\s*(\d+(?:(?: va)? \d+\b(?!\s*(?:gio|phut|thang)\b))+)',query):
        branches.update(re.findall(r'\d+',match[1]))
    named_branches=set()
    for branch, place in LIBRARY_CAMPUS_NAMES.items():
        if re.search(r'\b(?:'+place+r')\b',query):
            named_branches.add(branch)
    if not branches.issubset(LIBRARY_CAMPUSES) or (branches and named_branches and not named_branches.issubset(branches)):
        return None
    return branches | named_branches


def normalized_clock_query(question):
    return normalize(re.sub(r'(?<=\d):\s*(?=\d)','h',unquoted_text(question)))


def answer_library_hours(state, question, q, history):
    branch_query = q
    clock_query=normalized_clock_query(question)
    clock_matches=re.findall(r'\b'+HOURS_CLOCK,clock_query)
    date_pattern = r'\b(?:'+ '|'.join(DAY_OFFSETS) +'|'+HOURS_DAY+r'|ngay le|nghi le|tet)\b'
    if not asks_library_hours(q):
        campus_turn = q if HOURS_CAMPUS_FOLLOWUP.fullmatch(clock_query) else None
        date_turn = q if HOURS_FOLLOWUP.fullmatch(q) else None
        if not (campus_turn or date_turn or HOURS_TIME_FOLLOWUP.fullmatch(clock_query)):
            return None
        recent_hours = ''
        schedule = None
        for turn in reversed(history or []):
            if turn['role'] != 'user':
                if not recent_hours:
                    displayed = normalize(re.sub(r'\b\d{1,2}:\d{2}\b', ' ', turn['content']))
                    schedule=DISPLAYED_SCHEDULE.match(normalized_clock_query(turn['content']))
                    if schedule or displayed.startswith(('lich phuc vu ','thu vien uth ap dung lich chung ')):
                        recent_hours = displayed
                continue
            previous = normalize(unquoted_text(turn['content']))
            previous_clock=normalized_clock_query(turn['content'])
            clock_matches=clock_matches or re.findall(r'\b'+HOURS_CLOCK,previous_clock)
            if asks_library_hours(previous):
                branch_query = campus_turn or previous
                q = date_turn or previous
                break
            if previous in COURTESY:
                continue
            if HOURS_CAMPUS_FOLLOWUP.fullmatch(previous_clock):
                campus_turn = campus_turn or previous
            elif HOURS_FOLLOWUP.fullmatch(previous):
                date_turn = date_turn or previous
            elif not HOURS_TIME_FOLLOWUP.fullmatch(previous_clock):
                return None
        else:
            # A recent displayed schedule can outlast the original question in the six-message window.
            if not recent_hours:
                return None
            branch_query = campus_turn or recent_hours
            q = date_turn or (schedule['weekday'] if schedule else '')
            if schedule:
                if not clock_matches and schedule['hour']:
                    clock_matches=[(schedule['hour'],schedule['minute'],'')]
                if not date_turn and schedule['date']:
                    current=today()
                    q=next((term for term,delta in DAY_OFFSETS.items()
                            if (current+timedelta(days=delta)).strftime('%d %m %Y')==schedule['date']),None)
                    if q is None:
                        return result('Bạn muốn xem lịch cho ngày nào?', 'clarify')

    branches = requested_campuses(branch_query)
    if branches is None:
        return result('Bạn muốn xem giờ phục vụ ở cơ sở 1, 2 hay 3?', 'clarify')
    campuses = tuple(sorted(branches)) or LIBRARY_CAMPUSES
    branch = next(iter(branches)) if len(branches)==1 else None
    location = (f' tại cơ sở {branch}' if branch else ' tại cả ba cơ sở' if len(campuses)==3
                else f' tại cơ sở {campuses[0]} và {campuses[1]}')
    references = [HOURS_SOURCE]

    lunch = LUNCH_HOURS.search(q)
    contact = None
    if lunch or re.search(r'\b(lien he|hoi) o dau\b',q):
        contacts = [row for row in published_rows(state.db) if row['category']=='hours_contact']
        contact = max(contacts,key=lambda row:row['checked_at'],default=None)
    if lunch:
        answer=f'Lịch chung của thư viện chưa ghi rõ giờ nghỉ trưa{location}. Bạn nên xác nhận trước khi đến vào buổi trưa.'
        if contact:
            answer+='\n\n'+contact['answer']
            references.append(source(contact))
        return result(answer,'needs_confirmation',references)
    if contact:
        return result(contact['answer'],sources=[source(contact)])

    general = (f'Thư viện UTH áp dụng lịch chung{location}.\n'
               f'• Thứ Hai đến thứ Sáu: {WEEKDAY_HOURS[0]}.\n'
               f'• Thứ Bảy: {WEEKDAY_HOURS[5]}.\n'
               '• Chủ nhật và ngày Lễ, Tết: nghỉ phục vụ.')
    if not branch:
        general = f'Thư viện UTH áp dụng lịch chung{location}.\n'+campus_hours(
            f'Thứ Hai đến thứ Sáu {WEEKDAY_HOURS[0]} · Thứ Bảy {WEEKDAY_HOURS[5]} · Chủ nhật và ngày Lễ, Tết nghỉ phục vụ.',campuses=campuses)
    if re.search(r'\b(?:hai (?:nguon|moc)|ban huong dan khac)\b',q) and '20:30' in unquoted_text(question):
        older=next((row for row in published_rows(state.db) if row['category']=='hours_reference'
                    and '/uploads/2022/10/' in row['source_url'] and '07:30–20:30' in row['answer']),None)
        if older:
            answer=('Mốc 20:30 nằm ở trang 12 của hướng dẫn LIC lưu trong thư mục 2022/10, '
                    'ở phần giờ phục vụ từ thứ Hai đến thứ Sáu của cơ sở 1. Mốc 18:30 nằm ở trang 12 '
                    'của hướng dẫn lưu trong thư mục 2024/11, ở phần lịch chung từ thứ Hai đến thứ Sáu. '
                    'Bạn nên dùng mốc 18:30 theo lịch chung để lên kế hoạch. Nếu đi vào một ngày cụ thể, '
                    'hãy kiểm tra thông báo của thư viện xem cơ sở đó có lịch riêng hay không.')
            return result(answer,sources=[source(older),*references])
    if re.search(r'\b(nguon nao|hai nguon|ban huong dan khac|thuong le|mac dinh)\b',q):
        return result(general,sources=references)
    if re.search(r'\b(ngay le|nghi le|tet)\b',q):
        answer=f'Thư viện UTH nghỉ phục vụ{location} vào ngày Lễ, Tết theo lịch chung.'
        if not branch:
            answer+='\n'+campus_hours('nghỉ phục vụ',campuses=campuses)
        return result(answer,sources=references)

    q = re.sub(r'\bthu bya\b','thu bay',q)
    offsets = {DAY_OFFSETS[match] for match in re.findall(r'\b(?:'+ '|'.join(DAY_OFFSETS) +r')\b',q)}
    if not re.search(date_pattern,q) and re.search(r'\b'+HOURS_NOW+r'\b',q):
        offsets={0}
    day_matches = re.findall(r'\b(?:'+HOURS_DAY+r')\b',q)
    weekdays = {normalize(label): i for i,label in enumerate(WEEKDAY_LABELS)}
    weekdays.update({f'thu {i+2}': i for i in range(6)})
    days = {weekdays[match] for match in day_matches}
    clocks=set()
    for hour,minute,part in clock_matches:
        hours=int(hour)
        if 1<=hours<12 and (part in ('chieu','toi','pm') or part=='trua' and hours<=2):
            hours+=12
        elif hours==12 and part in ('sang','am'):
            hours=0
        clocks.add((hours,int(minute or 0)))
    if len(clocks)>1 or any(hour>23 or minute>59 for hour,minute in clocks):
        return result('Bạn muốn xem giờ phục vụ vào mấy giờ? Hãy gửi một giờ cụ thể, ví dụ 15:30.', 'clarify')
    clock=next((f'{hour:02d}:{minute:02d}' for hour,minute in clocks),None)
    if not clock and offsets=={0} and re.search(r'\b(?:bay gio|luc nay|'+HOURS_NOW+r')\b',q):
        clock=datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).strftime('%H:%M')
    midday=clock is not None and '12:00'<=clock<'13:00'
    if (len(offsets)>1 or len(days)>1 or (offsets and days)
            or re.search(r'\b(hom qua|tuan sau|tuan truoc|ngay \d+|thang \d+)\b',q)
            or re.search(r'\b\d{1,2}[/-]\d{1,2}\b',question)):
        return result('Bạn muốn xem lịch cho hôm nay, ngày mai hay một thứ cụ thể trong tuần?', 'clarify')
    midday_notice=f'Lịch chung chưa ghi rõ giờ nghỉ trưa{location}. Bạn nên xác nhận với thư viện trước khi đến lúc {clock}.'
    if not offsets and not days:
        if clock:
            if midday:
                return result(midday_notice,'needs_confirmation',references)
            service_days=[label for label,window in zip(WEEKDAY_LABELS,WEEKDAY_HOURS)
                          if clock_service(clock,window)=='trong khung giờ phục vụ']
            if not service_days:
                return result(f'{clock} nằm ngoài giờ phục vụ{location} theo lịch chung.\n\n'+general,sources=references)
            return result(f'Theo lịch chung{location}, {clock} nằm trong khung giờ phục vụ vào {", ".join(service_days)}.\n\n'+general,
                          sources=references)
        return result(general,sources=references)
    if not offsets:
        weekday = next(iter(days))
        hours = WEEKDAY_HOURS[weekday]
        if clock:
            if midday and weekday!=6:
                return result(midday_notice,'needs_confirmation',references)
            return result(f'{WEEKDAY_LABELS[weekday]}, {clock} nằm {clock_service(clock,hours)}{location} theo lịch chung.\n'
                          +campus_hours(hours,campuses=campuses),sources=references)
        if not branch:
            return result(f'{WEEKDAY_LABELS[weekday]}, lịch chung{location}.\n'+campus_hours(hours,campuses=campuses),sources=references)
        return result(f'{WEEKDAY_LABELS[weekday]}, thư viện UTH{location} {"nghỉ phục vụ" if weekday==6 else "phục vụ từ " + hours} theo lịch chung.',sources=references)

    selected = today()+timedelta(days=next(iter(offsets)))
    weekday = selected.weekday()
    with state.db() as db:
        rows = db.execute('''SELECT * FROM schedules WHERE weekday=? AND valid_from<=? AND valid_until>=?
                             ORDER BY branch,opens,id''',(weekday,selected.isoformat(),selected.isoformat())).fetchall()
    overrides = {}
    clock_overrides = {}
    for campus in campuses:
        candidates = [row for row in rows if row['branch']==campus]
        if not candidates:
            continue
        spans = [(date.fromisoformat(row['valid_until'])-date.fromisoformat(row['valid_from'])).days for row in candidates]
        shortest = min(spans)
        applicable = [row for row,span in zip(candidates,spans) if span==shortest]
        window = 'nghỉ phục vụ' if any(row['closed'] for row in applicable) else '; '.join(f"{row['opens']}–{row['closes']}" for row in applicable)
        if clock:
            clock_overrides[campus]=f'{clock_service(clock,window)} ({window})'
        notes = ' '.join(row['note'] for row in applicable if row['note'])
        overrides[campus]=f'{window}. {notes}'.strip()
        references.extend(source(row) for row in applicable)

    label = f'{WEEKDAY_LABELS[weekday]} {selected:%d/%m/%Y}'
    if clock:
        hours=WEEKDAY_HOURS[weekday]
        use_default=len(overrides)!=len(campuses)
        uncertain=use_default and midday and weekday!=6
        usual=('lịch chung chưa ghi rõ giờ nghỉ trưa' if uncertain else
               f'{clock_service(clock,hours)} theo lịch chung ({hours})')
        return result(f'{label}, lúc {clock}{location}.\n'+campus_hours(usual,clock_overrides,campuses),
                      'needs_confirmation' if uncertain else 'answered',references if use_default else references[1:])
    if branch and overrides:
        return result(f'Lịch phục vụ {label}.\nCơ sở {branch} — {overrides[branch]}',sources=references[1:])
    hours = WEEKDAY_HOURS[weekday]
    if not branch:
        opening=f'Lịch phục vụ {label}{location}.'
        return result(opening+'\n'+campus_hours(hours+' (lịch chung)',overrides,campuses),
                      sources=references[1:] if len(overrides)==len(campuses) else references)
    window = 'nghỉ phục vụ' if weekday==6 else f'phục vụ từ {hours}'
    return result(f'{label}, thư viện UTH{location} {window} theo lịch chung.',sources=references)


def library_subject(question):
    return bool(re.search(r'\b(thu vien|opac|uth|lic|sach|tai lieu|luan van|luan an|khoa luan|do an|giao trinh|bai giang|gia han|qua han|han tra|muon tra|mo cua|dong cua|gio phuc vu|lich phuc vu|proquest|stinet|xep gia|isbn|ddc|ebook)\b',normalize(question)))


def outside_definition(question):
    return bool(re.search(r'\b(la gi|nghia la gi|dinh nghia|khai niem|giai thich)\b',normalize(question))) and not library_subject(question)


def library_question(question,history=None):
    if library_subject(question):
        return True
    followup=r'^(con|vay|the|thi|bao nhieu|khi nao|may gio|o dau|duoc khong|co khong|co phuc vu|ngay|hom nay|mai|thu|chu nhat|tai sao|vi sao|gi|sao|them|tiep|khac)\b'
    if outside_definition(question) or not re.search(followup,normalize(question)):
        return False
    for turn in reversed((history or [])[-6:]):
        if turn['role']=='user':
            if library_subject(turn['content']):
                return True
            if not re.search(followup,normalize(turn['content'])):
                break
    return False


def library_redirect(question):
    if not outside_definition(question) and len(normalize(question).split())<=3:
        return result('Bạn muốn tìm sách hoặc tài liệu về chủ đề này, hay cần hỗ trợ dịch vụ nào của thư viện? Hãy cho mình thêm tên tài liệu, tác giả hoặc nhu cầu tra cứu nhé.', 'clarify',suggestions=SUGGESTIONS)
    return result('Mình là chatbot dành riêng cho thư viện UTH, hỗ trợ tìm tài liệu, tra cứu OPAC, mượn/gia hạn, giờ phục vụ và tài nguyên điện tử. Mình không trả lời kiến thức chung ngoài phạm vi này. Nếu bạn muốn tìm tài liệu về chủ đề đang hỏi, hãy cho mình tên sách hoặc chủ đề cần tra cứu.', 'not_found',suggestions=SUGGESTIONS)


def book_metadata(book,attributes):
    labels={'isbn':'ISBN','shelf':'vị trí kệ / ký hiệu xếp giá','publisher':'nhà xuất bản',
            'author':'tác giả','year':'năm xuất bản','summary':'tóm tắt nội dung','audience':'đối tượng đọc','format':'dạng tài liệu'}
    lines=[]
    facts=[]
    missing=[]
    sources=[]
    for field in attributes:
        label=labels[field]
        checked_at=book['checked_at']
        if field in ('author','year') and book[field].strip():
            facts.append(('có tác giả là ' if field=='author' else 'xuất bản năm ')+book[field])
        elif field=='format' and book['kind']=='digital':
            facts.append('là tài liệu số')
        elif field=='format' and 'dang tai lieu sach truyen thong' in normalize(book['description']):
            facts.append('là sách giấy')
        elif field in ('summary','audience') and book.get('marc',{}).get(field):
            lines.append(f"{label[0].upper()+label[1:]}:\n\n{book['marc'][field]}")
            checked_at=book['marc']['checked_at']
        elif field=='summary' and book['description'].strip():
            lines.append(f"{book['description']}\n\nĐây là phần mô tả trong biểu ghi. Mình chưa kiểm chứng toàn văn.")
            missing.append(label)
        else:
            missing.append(label)
        citation={'title':book['title'],'url':book['url'],'checked_at':checked_at}
        if citation not in sources:
            sources.append(citation)
    opening=f"“{book['title']}”"+(' '+', '.join(facts)+'.' if facts else '')
    if missing:
        lines.append('Biểu ghi đang có chưa xác nhận '+', '.join(missing)+'. Bạn hãy mở nguồn gốc hoặc hỏi thư viện; mình không tự suy đoán thông tin này.')
    return '\n\n'.join([opening,*lines]),'needs_confirmation' if missing else 'answered',sources


def answer_question(state, question, history=None):
    if len(question)>MAX_MODEL_MESSAGE_CHARS:
        return result('Mình đã nhận đầy đủ tin nhắn, nhưng nội dung vượt khả năng đọc trong một lượt của mô hình đang dùng. Bạn hãy chia thành các phần nhỏ hơn hoặc gửi riêng câu hỏi và đoạn cần hỗ trợ. Mình không âm thầm cắt nội dung để trả lời như đã đọc hết.', 'clarify')
    original_question=question
    question=search_correction(question)
    original_q=normalize(question)
    unquoted=unquoted_text(question)
    intent_q=normalize(unquoted)
    if re.fullmatch(r'(?:ma )?isbn (?:la gi|nghia la gi|dung de lam gi)(?: a)?',intent_q):
        return result('ISBN là mã số sách tiêu chuẩn quốc tế. Mã này giúp nhận diện một nhan đề, ấn bản và dạng xuất bản cụ thể. Bản in và ebook của cùng một nhan đề có thể có mã ISBN riêng.',
                      sources=[{'title':'International ISBN Agency — What is an ISBN?',
                                'url':'https://www.isbn-international.org/content/what-isbn/10','checked_at':None}])
    other_reader=re.search(r'\b(nguoi khac|ban cung lop|ban ay|ban khac|sinh vien khac|doc gia khac|ban doc khac)\b',intent_q)
    named_reader_loans=re.search(r'\b(?:cho (?:toi|minh|em) biet|kiem tra (?:giup (?:toi|minh|em))?) '
        r'(?:ban|sinh vien|doc gia) (?!(?:co|dang|da|toi|minh|em)\b)(?:[a-z]+ ){1,4}(?:dang muon|muon sach)\b',intent_q)
    private_loan_data=re.search(r'\b(lich su|dang muon|han tra|ngay tra|tai khoan)\b',intent_q)
    if named_reader_loans or (other_reader and private_loan_data):
        own_loans=[row for row,_ in keyword_search('Xem những sách tôi đang mượn ở đâu?',published_rows(state.db)) if row['category']=='opac' and row['status'] in ('reviewed_public','verified')][:1]
        answer='Mình không thể xem hoặc tiết lộ lịch sử mượn, hạn trả hay tài khoản của người khác. Bạn chỉ có thể đăng nhập tài khoản của bạn để xem thông tin được phép truy cập; nếu cần hỗ trợ nghiệp vụ, hãy liên hệ thư viện.'
        return result(answer+''.join('\n\nVới sách của chính bạn: '+row['answer'] for row in own_loans),'not_found',[source(row) for row in own_loans])
    if re.match(r'^(?:(?:toi|minh|em) )?(?:dung|khong(?: muon)?) (?:tim|tra cuu)(?! (?:thay|duoc|ra)\b)\b',intent_q):
        boundary=next(question_clause_ends(question),len(question))
        followup=question[boundary:].strip()
        if re.match(r'^(?:(?:vay|the) )?(?:(?:toi|minh|em) (?:muon|can) (?:hoi )?)?'
                    r'(?:lam the nao|lam sao|huong dan|cach)\b',normalize(followup)) and library_subject(followup):
            return answer_question(state,followup)
        return result('Bạn không muốn tra cứu theo yêu cầu này. Bạn muốn đổi chủ đề sách hay cần hỗ trợ dịch vụ nào của thư viện?','clarify')
    if re.search(r'\b(?:cu|hay|thu) doan\b',intent_q) and re.search(r'\b(?:phi|'+PENALTY_WORD+r')\b',intent_q):
        fees=[row for row in published_rows(state.db) if row['category']=='fees']
        return result('Mình chưa có căn cứ để xác nhận mức phí bạn nêu. Hãy hỏi thư viện về mức phí áp dụng cho khoản mượn của bạn.',
                      'needs_confirmation',[source(row) for row in fees])
    clauses=map(normalize,re.split(r'[.!?;](?=\s|$)|\n',unquoted))
    asks_unverified_claim=any(
        (re.search(r'(?:^|\bva )(?:hay )?(?:(?:noi|bao|ghi) rang|xac nhan(?: rang)?|(?:noi|bao|ghi) da)\b',clause) or
         re.search(r'\bgia vo\b',clause) or
         re.search(r'\bcoi (?:\w+ ){0,12}la lenh quan tri\b',clause)) and
        (claims_completed_transaction(clause) or re.search(r'\b(?:con|co) (?:dung )?\d+ ban (?:roi|trong)\b',clause))
        for clause in clauses
    )
    if asks_unverified_claim:
        notice='Chatbot chưa thực hiện giao dịch. Bạn có thể vào Trang cá nhân trên OPAC để kiểm tra khoản mượn.'
        if re.search(r'\b(?:con|co) (?:dung )?\d+ ban (?:roi|trong)\b',intent_q):
            notice+=' Chatbot chưa kiểm tra số bản rỗi. Hãy xem mục Thông tin xếp giá để đối chiếu.'
        lookups=explicit_metadata_lookups(question)
        if len(lookups)==1:
            (field,query),attributes=next(iter(lookups.items()))
            candidates=[]
            for book in search_books(state,query,field=field):
                values=book['author'].split(';') if field=='author' else [book['title']]
                if any(normalize_catalog(value)==query for value in values):
                    candidates.append(book)
            if len(candidates)==1:
                book=candidates[0]
                answer,_,sources=book_metadata(book,sorted(attributes))
                return {**result(answer+'\n\n'+notice,'needs_confirmation',sources,mode='catalog'),'books':[book],
                        'context_query':'Tìm theo nhan đề '+book['title']}
        return result(notice,'clarify')
    if getattr(state.settings,'demo_reservations',False) and re.search(r'\b(?:sach mau|thu vien mau)\b',intent_q):
        if re.search(r'\b(?:nhan sach|gia han|tra sach|han tra)\b',intent_q):
            return result('Mở Thư viện mẫu và đăng nhập để xem khoản mượn. Sau khi đăng ký, chọn “Nhận sách” để có hạn trả 7 ngày. '
                          'Bạn có thể gia hạn một lần thêm 7 ngày nếu chưa quá hạn, hoặc chọn “Trả sách” để trả bản mẫu.',mode='demo_reservation')
    if re.search(r'\b(lien thu vien|mltv)\b',intent_q):
        policies=[row for row in published_rows(state.db) if row['category']=='interlibrary']
        if policies:
            return result('\n\n'.join(row['answer'] for row in policies),'needs_confirmation',[source(row) for row in policies])
        return result('Mình chưa có thông tin về dịch vụ mượn liên thư viện. Bạn có thể hỏi thư viện đã cấp tài khoản cho mình.','not_found')
    reservation_request = re.match(r'^(?:(?:vay|the|ban|toi|minh|em|co|the|muon|hay|giup|vui|long) )*(?:dang k[iy] (?:muon|sach)|dat cho (?:muon|sach)|dat muon)\b', intent_q)
    reservation_guidance = re.search(r'\b(?:khac|co phai|gia han|the nao|lam sao|opac)\b', intent_q)
    chat_borrow = re.fullmatch(
        r'(?:(?:vay|the|toi|minh|em|ban) )*(?:(?:co(?: the)?|muon) )?(?:dang k[iy] )?muon '
        r'(?:sach|tai lieu|(?:cuon|quyen)(?: sach)?)(?: (?:nay|do|ay))? '
        r'(?:(?:ngay|truc tiep) )?(?:(?:tai|o) day|(?:qua|tren|trong) (?:chatbot|(?:(?:doan|khung|o) )?chat)(?: nay)?)'
        r'(?: (?:duoc )?khong)?(?: a)?', intent_q)
    if chat_borrow or (reservation_request and not reservation_guidance):
        opening='Bạn chưa thể mượn sách thật ngay trong chatbot. ' if chat_borrow else ''
        if getattr(state.settings, 'demo_reservations', False):
            return result(opening+'Bạn có thể đăng ký mượn tại Thư viện mẫu. Hãy đăng nhập, chọn sách mẫu và xác nhận yêu cầu. Yêu cầu được lưu trong kho giả lập.', mode='demo_reservation')
        return result(opening+'Bạn có thể đăng ký mượn trên OPAC. Mở biểu ghi, đăng nhập bằng tài khoản thư viện và chọn “Đăng ký mượn” nếu có. Sau đó, kiểm tra yêu cầu trong Trang cá nhân.',
                      sources=[{'title':'Mở OPAC thư viện','url':'https://opacthuvien.ut.edu.vn/opac/','checked_at':None},
                               {'title':'Hướng dẫn đăng ký mượn trên OPAC','url':'https://opacthuvien.ut.edu.vn/opac/Upload/HDSD_TRACUU_OPAC.v1.1.pdf#page=7','checked_at':None}])
    for conjunction in re.finditer(r'\b(?:va|dong thoi|sau do)\b',intent_q):
        before,after=intent_q[:conjunction.start()].strip(),intent_q[conjunction.end():].strip()
        if (search_guidance(before) and is_book_request(after)) or (is_book_request(before) and re.match(r'^(?:huong dan|cach|lam the nao|lam sao)\b',after) and search_guidance(after)):
            return result('Bạn muốn tìm tài liệu cụ thể và hỏi cách tra cứu. Hãy gửi riêng từng yêu cầu để mình trả đúng sách và đúng hướng dẫn.', 'clarify',suggestions=SUGGESTIONS)
    for conjunction in re.finditer(r'\s+(?:và|va|rồi|roi)\s+',question,flags=re.I):
        lookup=question[:conjunction.start()]
        followup=question[conjunction.end():]
        if unquoted != unquoted_text(lookup)+conjunction[0]+unquoted_text(followup):
            continue
        if is_borrowing_procedure(followup):
            topic=re.fullmatch(r'(?:thu vien(?: uth)? )?co (?:nhung )?(?:sach|tai lieu) nao (?:ve|chu de) (.+)',
                               normalize_catalog(lookup))
            if topic or is_book_request(lookup):
                listing=answer_question(state,'Tìm sách '+topic[1] if topic else lookup,history)
                guide=answer_question(state,followup)
                return {**listing,'answer':listing['answer']+'\n\n'+guide['answer'],
                        'sources':result('',sources=listing['sources']+guide['sources'])['sources'],
                        'status':guide['status'] if listing['status']=='answered' else listing['status']}
        position=book_position(followup)
        if position is None or not is_book_request(lookup):
            continue
        details=re.sub(r'\s+(?:cua )?(?:cuon|quyen|sach|tai lieu)(?: sach)? (?:dau tien|thu (?:nhat|mot|hai|ba|tu|bon|nam|\d{1,3}))(?: a)?$',
                       '',normalize(followup))
        attributes=book_attributes(details)
        if not attributes or 'availability' in attributes or not book_reference(details):
            continue
        listing=answer_question(state,lookup,history)
        books=listing.get('books',[])
        if listing['status']!='answered' or not books:
            return listing
        if not 1<=position<=len(books):
            return {**result(f'Mình tìm được {len(books)} tài liệu. Bạn hãy chọn một cuốn trong danh sách để mình tra thông tin.',
                             'clarify',listing['sources'],mode='catalog'),'books':books,'context_query':listing.get('context_query','')}
        book=books[position-1]
        answer,status,sources=book_metadata(book,attributes)
        return {**result(answer,status,sources,mode='catalog'),'books':[book],'context_query':'Tìm theo nhan đề '+book['title'],
                'list_book_ids':[item['id'] for item in books]}
    edited_book=edited_book_year_question(question)
    direct=('year',edited_book[0]) if edited_book else direct_document_question(question)
    if not direct and unquoted!=question and book_attributes(intent_q) and not search_guidance(question) and not is_borrowing_procedure(question):
        return result('Mình chưa xác định được một nhan đề duy nhất trong yêu cầu này. Bạn hãy hỏi riêng từng tài liệu và thông tin cần tra cứu để mình đối chiếu đúng biểu ghi.','clarify')
    reference_context=any(turn['role']=='assistant' and 'book_ids' in turn for turn in history or [])
    ids=[]
    list_book_ids=[]
    for turn in reversed(history or []):
        if turn['role']=='assistant' and turn.get('book_ids'):
            ids=turn['book_ids']
            remembered_list=turn.get('list_book_ids',[])
            if len(ids)>1:
                list_book_ids=ids
            elif ids[0] in remembered_list:
                list_book_ids=remembered_list
            break
        if turn['role']=='user' and normalize(turn['content']) not in COURTESY:
            if is_book_request(turn['content']) or direct_document_question(turn['content']) or book_position(turn['content']) is not None or not book_followup(turn['content']):
                break
    position=book_position(question) if not direct and not is_book_request(question) else None
    ordinal=position is not None
    relative=not direct and not is_book_request(question) and book_reference(question)
    if edited_book:
        # The title and editor are search data, not additional service requests.
        intent_q='nam xuat ban'
    attributes=book_attributes(intent_q)
    metadata_requested=re.search(r'\b(?:ban ghi (?:thu vien )?ghi|giup (?:toi|minh|em) xac dinh)\b',intent_q)
    if metadata_requested:
        if re.search(r'\b(?:nhung nguoi tham gia|tac gia)\b',intent_q) and 'author' not in attributes:
            attributes.append('author')
        if re.search(r'\btac gia va nam\b',intent_q) and 'year' not in attributes:
            attributes.append('year')
        if re.search(r'\b(?:sach giay hay tai lieu so|tai lieu so hay sach giay)\b',intent_q):
            attributes.append('format')
    if position is None and relative and reference_context:
        if len(ids)==1:
            position=1
        else:
            books=[book for row_id in ids if (book:=public_book(state.db,row_id))]
            return {**result('Bạn đang hỏi về tài liệu nào? Hãy chọn nhan đề hoặc thứ tự trong danh sách để mình đối chiếu đúng biểu ghi.','clarify'),'books':books}
    selected_book=None
    lookup_text=question
    kind_followup=book_format_filter(question) if position is None and not direct else None
    if kind_followup:
        context=contextual_question(question,history)
        if context==question or not (query:=book_query(context)) or len(query)>200:
            return result('Bạn muốn tìm tài liệu theo dạng này về chủ đề nào? Hãy gửi nhan đề hoặc từ khóa để mình tra danh mục.', 'clarify')
        field=(structured_book_query(context) or ('all',query))[0]
        books,semantic_status=search_books_with_status(state,query,kind_followup,field)
        books=books[:5]
        label='tài liệu số' if kind_followup=='digital' else 'sách và tài liệu khác'
        if not books:
            return result(f'Mình chưa tìm thấy kết quả cho nhóm {label} theo chủ đề này.',
                          'needs_confirmation' if semantic_status else 'not_found',mode='catalog')
        answer=f'Mình tìm được {len(books)} biểu ghi thuộc nhóm {label} theo chủ đề đang tra cứu.'
        if kind_followup=='books':
            answer+=' Hãy xem dạng tài liệu trong biểu ghi để xác nhận bản in.'
        return {**result(answer,sources=[{'title':b['title'],'url':b['url'],'checked_at':b['checked_at']} for b in books],mode='catalog'),
                'books':books,'context_query':context}
    if position is not None:
        # A metadata reply shows one book. An ordinal can still refer to the preceding results list.
        if ordinal and not list_book_ids and len(ids)==1:
            for turn in reversed(history or []):
                if turn['role']=='assistant' and len(turn.get('book_ids',[]))>1:
                    list_book_ids=turn['book_ids']
                    break
                if turn['role']=='user' and normalize(turn['content']) not in COURTESY:
                    if is_book_request(turn['content']) or book_format_filter(turn['content']) or not book_followup(turn['content']):
                        break
        if ordinal and list_book_ids:
            ids=list_book_ids
        multiple_fields=relative and len(attributes)>1 and len(re.findall(r'\b(?:tai lieu|(?:cuon|quyen)(?: sach)?|sach)\b',intent_q))<=1 and 'hoac' not in intent_q.split()
        if 1<=position<=len(ids) and (multiple_fields or not re.search(r'\b(va|hoac)\b',intent_q)):
            selected_book=public_book(state.db,ids[position-1])
        if not selected_book:
            return result('Mình chưa xác định được tài liệu theo thứ tự này trong danh sách vừa hiển thị. Bạn hãy gửi nhan đề cụ thể hoặc tìm lại sách để mình đối chiếu đúng biểu ghi công khai.','clarify')
        question='Tìm theo nhan đề '+selected_book['title']
    else:
        question='Tìm theo nhan đề '+direct[1] if direct else contextual_question(question,history)
    guidance=search_guidance(question,allow_bare=True)
    # Natural borrowing requests may also ask for instructions in the same turn.
    borrowing=bool(re.search(r'\b(muon|roi|tinh trang|so ban)\b',intent_q))
    natural=re.search(r'\bco (?:nhung )?(?:sach|tai lieu) (.+?) (?:nao\b|co the\b|dang roi\b|con roi\b)',normalize_catalog(lookup_text)) if borrowing and not guidance else None
    if natural:
        question='Tìm sách '+natural[1]
    if len(question)>MAX_MODEL_MESSAGE_CHARS:
        return result('Ngữ cảnh tài liệu trước quá dài cho một lượt xử lý. Bạn hãy gửi lại tên/chủ đề sách ngắn gọn hoặc chia nội dung thành các phần; mình không âm thầm cắt ngữ cảnh để tìm kiếm.', 'clarify')
    q = normalize(question)
    ebook_topic=re.fullmatch(
        r'(?:(?:toi|minh|em) )?(?:co the |muon |can )?(?:tim|kiem|tra cuu) (?:ebook|sach dien tu|tai lieu so)'
        r'(?: (tieng viet|tieng anh))? (?:ve|chu de) (.+?)(?: (?:tai|o|trong) thu vien(?: uth)?)?(?: (?:duoc )?khong)?',normalize_catalog(question))
    if ebook_topic and not guidance:
        if len(ebook_topic[2])>200 or re.search(r'\b(?:khong phai|ngoai tru|loai tru|dung lay|khong can|bo qua|va (?:cach|gio|phi|han|thu tuc|huong dan))\b',ebook_topic[2]):
            return result('Bạn hãy gửi riêng chủ đề tài liệu số cần tìm để mình kiểm tra đúng danh mục.', 'clarify')
        books,semantic_status=search_books_with_status(state,ebook_topic[2],kind='digital')
        if books:
            books=books[:5]
            answer='Mình tìm được các biểu ghi tài liệu số theo chủ đề bạn hỏi. Mở biểu ghi để kiểm tra quyền đọc hoặc tải.'
            if ebook_topic[1]:
                language='tiếng Việt' if ebook_topic[1]=='tieng viet' else 'tiếng Anh'
                answer+=f' Danh mục chưa đủ thông tin để xác nhận tất cả tài liệu này bằng {language}.'
            return {**result(answer,sources=[{'title':b['title'],'url':b['url'],'checked_at':b['checked_at']} for b in books],mode='catalog'),
                    'books':books,'context_query':'Tìm sách '+ebook_topic[2]}
        status='needs_confirmation' if semantic_status else 'not_found'
        answer='Mình chưa tìm thấy biểu ghi tài liệu số phù hợp trong danh mục hiện có. Bạn có thể thử tra cứu trên OPAC.'
        return result(answer,status,sources=[{'title':'Mở OPAC thư viện','url':'https://opacthuvien.ut.edu.vn/opac/','checked_at':None}],mode='catalog')
    if q==original_q and book_followup(intent_q) and book_attribute(intent_q) and not is_book_request(question):
        return result('Bạn đang hỏi về tài liệu nào? Vui lòng cung cấp nhan đề hoặc tìm sách trước để mình đối chiếu đúng biểu ghi.', 'clarify',suggestions=['Tìm sách Olympic cơ học'])
    asks_return_date = bool(re.search(r'\b(?:bao gio|khi nao) (?:\w+ ){0,3}tra\b', intent_q))
    if 'muon sach' in intent_q and asks_return_date and not is_borrowing_procedure(question):
        question='Thời hạn mượn sách'
        q=normalize(question)
    if re.fullmatch(r'(xin chao|chao|hello|hi|alo)( ban| thu vien| tro ly)?',q):
        return result('Chào bạn! Mình có thể hỗ trợ tra cứu OPAC, hướng dẫn tài nguyên điện tử và thông tin dịch vụ thư viện.',suggestions=SUGGESTIONS)
    if q in COURTESY:
        return result('Rất vui được hỗ trợ bạn. Khi cần tìm tài liệu hoặc hỏi về dịch vụ thư viện, bạn cứ nhắn mình nhé.',suggestions=SUGGESTIONS)
    if is_book_request(question):
        if re.search(r'\b(khong phai|ngoai tru|loai tru|dung lay|khong can|bo qua|mo cua|gio phuc vu|gia han|phi|'+PENALTY_WORD+r'|qua han|han tra|thoi han|thoi gian muon|muon bao lau|bao nhieu ngay)\b',intent_q) or (natural and re.search(r'\bva (?:sach|tai lieu)\b',intent_q)):
            return result('Câu hỏi có điều kiện loại trừ hoặc nhiều yêu cầu khác nhau. Bạn vui lòng hỏi riêng tên/chủ đề sách cần tìm, sau đó hỏi về dịch vụ để mình đối chiếu đúng từng nguồn.', 'clarify',suggestions=SUGGESTIONS)
        query=book_query(question)
        if not selected_book and len(query)>200:
            return result('Từ khóa tra cứu quá dài để đối chiếu danh mục trong một lượt. Bạn hãy gửi tên tài liệu, tác giả hoặc chủ đề ngắn hơn; tin nhắn đã nhận không bị cắt để tìm kiếm.', 'clarify')
        if not query:
            return result('Bạn muốn tìm sách về chủ đề hoặc kỹ năng nào? Cho mình biết tên tài liệu, tác giả hoặc nhu cầu học tập để mình chọn đúng tài liệu.', 'clarify')
        if query:
            recommendation=None
            semantic_status=None
            structured=structured_book_query(question)
            if selected_book:
                books=[selected_book]
            elif structured:
                books=search_books(state,query,field=structured[0])
                if direct:
                    title=direct[1]
                    exact=[book for book in books if normalize_catalog(book['title'])==title]
                    if not exact and not edited_book and len(title.split())>=2:
                        prefixes=[book for book in books if normalize_catalog(book['title']).startswith(title+' ')]
                        if len(prefixes)>1:
                            exact=prefixes
                        elif prefixes:
                            main,separator,_=prefixes[0]['title'].partition(':')
                            if separator and normalize_catalog(main)==title:
                                exact=prefixes
                    books=exact
                if edited_book:
                    editor=edited_book[1]+' chu bien'
                    books=[book for book in books if any(normalize_catalog(name)==editor for name in book['author'].split(';'))]
            elif is_recommendation_request(question) and not author_query(question) and book_attribute(intent_q) in (None,'availability'):
                recommendation=recommend_books(state,question)
                books=recommendation['books']
                semantic_status=recommendation.get('semantic_status')
                query=recommendation['query']
                if not query:
                    return result('Bạn muốn tìm sách về chủ đề hoặc kỹ năng nào? Cho mình biết ngành học và mục tiêu, mình sẽ gợi ý tài liệu có trong danh mục thư viện.', 'clarify')
                question='Tìm sách '+query
                if history and re.fullmatch(r'(?:co cuon nao )?(?:danh cho )?(?:nguoi moi(?: bat dau)?|nang cao)(?: khong)?',original_q):
                    question=contextual_question('Tác giả',history)
            elif author_query(question):
                books=search_books(state,query,field='author')
                selection=selected_title([{'role':'user','content':question}])
                titles=[b for b in search_books(state,selection,field='title') if normalize_catalog(b['title'])==selection] if selection else []
                if books and titles:
                    choices=list({b['id']:b for b in titles+books}.values())[:5]
                    return {**result('Cụm từ có thể là nhan đề hoặc tên tác giả. Bạn hãy mở Tra cứu tài liệu và chọn “Nhan đề” hoặc “Tác giả” để xác định.','clarify'),
                            'books':choices,'context_query':question}
                books=titles or books
            else:
                books,semantic_status=search_books_with_status(state,query)
            attribute=direct[0] if direct else book_attribute(intent_q)
            if direct and attribute not in attributes:
                attributes=[attribute,*attributes]
            if direct and not edited_book and len(books)>1:
                choices=books[:5]
                return {**result('Mình tìm thấy nhiều biểu ghi khớp nhan đề bạn hỏi. Hãy xem tác giả và năm xuất bản, rồi chọn theo thứ tự, ví dụ “Cuốn thứ hai”.',
                                 'clarify',sources=[{'title':b['title'],'url':b['url'],'checked_at':b['checked_at']} for b in choices],
                                 mode='catalog'),'books':choices,'context_query':question}
            if history and book_followup(original_q) and attribute:
                selection=selected_title(history)
                exact=[b for b in books if normalize_catalog(b['title'])==selection]
                if exact:
                    books=exact
            books=books[:5]
            if books:
                answer=f'Mình tìm được {len(books)} tài liệu phù hợp. Bạn có thể xem thông tin và mở nguồn thư viện bên dưới; tình trạng còn sách và quyền truy cập có thể thay đổi.'
                status='answered'
                answer_sources=[]
                if recommendation:
                    answer=f'Mình gợi ý {len(books)} tài liệu dưới đây. Bạn có thể mở từng nhan đề để xem nội dung trước khi chọn.'
                    if recommendation['level_unconfirmed']:
                        answer+=' Thông tin hiện có chưa xác nhận mức độ bạn yêu cầu. Đây là các tài liệu cùng chủ đề; bạn nên xem mô tả để chọn cuốn phù hợp với kiến thức nền.'
                        status='clarify'
                if attribute=='availability' or (borrowing and natural):
                    if len(attributes)>1:
                        return {**result('Bạn đang hỏi tình trạng còn sách và thông tin biểu ghi. Hãy hỏi riêng từng phần để mình kiểm tra đúng nguồn và thời điểm.','clarify'),'books':books,'context_query':question}
                    checked=[]
                    # At most two public detail reads per turn; do not scan every hit.
                    candidates=[b for b in books if b['kind']=='books' and re.fullmatch(r'https://opacthuvien\.ut\.edu\.vn/opac/ODetail\.aspx\?intItemId=[1-9][0-9]*',b['url'])][:2]
                    for book in candidates:
                        snapshot=get_availability(book['url'])
                        book['availability_snapshot']=snapshot
                        checked.append((book,snapshot))
                    lines=[]
                    for book,snapshot in checked:
                        if snapshot['status']=='unknown':
                            lines.append('• '+book['title']+': Chưa kiểm tra được số bản rỗi trên OPAC.')
                        else:
                            when=datetime.fromisoformat(snapshot['checked_at']).astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).isoformat(timespec='seconds')
                            lines.append(f"• {book['title']}: OPAC hiển thị {snapshot['available']}/{snapshot['total']} bản rỗi (kiểm tra {when}).")
                    answer='\n'.join(lines) if lines else 'Các biểu ghi tìm được chưa cung cấp trạng thái bản rỗi có thể kiểm tra trực tiếp.'
                    answer+='\n\nCó bản rỗi là thông tin OPAC tại thời điểm kiểm tra; chưa phải xác nhận đặt mượn thành công hay bảo đảm đủ điều kiện mượn. Những biểu ghi khác bên dưới chưa được kiểm tra trạng thái. Tài liệu số không được suy ra là sách có thể mượn bản in.'
                    status='answered' if checked and any(s['status']!='unknown' for _,s in checked) else 'needs_confirmation'
                    if re.search(r'\b(huong dan|qua trinh|quy trinh|cach)\b',original_q) and re.search(r'\bdang k[iy] muon\b',original_q):
                        answer+='\n\nĐăng ký mượn: mở liên kết biểu ghi gốc, xem Thông tin xếp giá và nút “Đăng ký mượn”. Nếu OPAC yêu cầu, đăng nhập trực tiếp tại OPAC bằng tài khoản thư viện của bạn rồi thực hiện các bước và kiểm tra thông báo kết quả trên màn hình. Nếu không có nút hoặc không gửi được yêu cầu, liên hệ thư viện. Không gửi mật khẩu vào chat; chatbot chưa gửi giao dịch thay bạn.'
                elif ((selected_book and attribute) or direct or attribute in ('summary','audience')
                      or (history and book_followup(original_q) and attribute)
                      or (len(books)==1 and attributes and metadata_requested)):
                    if len(books)>1:
                        if edited_book:
                            return {**result('Mình tìm thấy nhiều biểu ghi cùng nhan đề và chủ biên. Bạn có thể đối chiếu năm xuất bản của từng bản bên dưới.','clarify',mode='catalog'),'books':books,'context_query':question}
                        return {**result('Có nhiều tài liệu trong ngữ cảnh. Bạn vui lòng chọn nhan đề cụ thể.','clarify',suggestions=['Tìm sách '+b['title'] for b in books[:3]]),'books':books,'context_query':question}
                    answer,status,answer_sources=book_metadata(books[0],attributes)
                suggestions=[]
                if recommendation and not attribute and not (borrowing and natural):
                    if not recommendation['level']:
                        suggestions.append('Em mới học')
                    if books[0].get('marc',{}).get('summary'):
                        suggestions.append('Tóm tắt cuốn đầu tiên')
                return {**result(answer,status,sources=answer_sources or [{'title':b['title'],'url':b['url'],
                                 'checked_at':b['checked_at']} for b in books],
                                 suggestions=suggestions,
                                 mode='catalog_ai' if recommendation and recommendation['used_model'] else 'catalog'),
                        'books':books,'context_query':question,'list_book_ids':list_book_ids if selected_book else []}
            url='https://opacthuvien.ut.edu.vn/opac/Oshow.aspx?'+urlencode({'rdSearchOption':0,'txtSearch':query})
            if edited_book:
                return result('Mình chưa tìm thấy biểu ghi khớp cả nhan đề và chủ biên. Bạn có thể mở OPAC để đối chiếu cách ghi tên hoặc ấn bản.','not_found',
                              sources=[{'title':'Tìm trực tiếp trên OPAC','url':url,'checked_at':None}],mode='catalog')
            if semantic_status:
                notice='Phần tìm theo nội dung đang chuẩn bị.' if semantic_status=='preparing' else 'Phần tìm theo nội dung tạm thời chưa sẵn sàng.'
                return {**result('Chưa thấy kết quả theo từ khóa. '+notice+' Bạn có thể thử lại hoặc mở OPAC.',
                                 'needs_confirmation',sources=[{'title':'Tìm trực tiếp trên OPAC','url':url,'checked_at':None}],
                                 suggestions=[original_question],mode='catalog'),'books':[],'context_query':question}
            return {**result('Chưa có biểu ghi phù hợp trong danh mục đã rà soát của chatbot. Điều này không chứng minh thư viện không có sách. Bạn có thể tìm tiếp trên OPAC hoặc nhập tên/tác giả cụ thể hơn.',
                            'not_found',sources=[{'title':'Tìm trực tiếp trên OPAC','url':url,'checked_at':None}]),'books':[],'context_query':question}
    hours_answer = answer_library_hours(state,question,q,history)
    if hours_answer is not None:
        if hours_answer['status']=='clarify':
            return hours_answer
        if re.search(r'\b(?:(?:dia chi|vi tri) (?:cua )?thu vien|thu vien(?: uth)? o dau)\b',q):
            directory=[row for row in published_rows(state.db) if row['category']=='branch_directory' and row['status'] in ('reviewed_public','verified')]
            if directory:
                row=max(directory,key=lambda row:row['checked_at'])
                campuses=requested_campuses(q)
                addresses=[line for line in row['answer'].splitlines() if (match:=re.match(r'^• Cơ sở ([123])\b',line))
                           and (not campuses or match[1] in campuses)]
                if addresses:
                    hours_answer=result('Địa chỉ thư viện\n'+'\n'.join(addresses)+'\n\n'+hours_answer['answer'],
                                        hours_answer['status'],[source(row),*hours_answer['sources']])
            if not directory or not addresses:
                hours_answer=result('Mình chưa có địa chỉ đã đối chiếu cho cơ sở bạn hỏi.\n\n'+hours_answer['answer'],
                                    'needs_confirmation',hours_answer['sources'])
        if GROUP_ROOM.search(intent_q):
            room=max((row for row in published_rows(state.db) if row['category']=='support'
                      and GROUP_ROOM.search(normalize(row['question']))),key=lambda row:row['checked_at'],default=None)
            notice='Mình chưa xác nhận được cơ sở bạn hỏi có phòng học nhóm hay không.'
            if room:
                notice+='\n\n'+room['answer']
            else:
                notice+=' Bạn có thể hỏi trực tiếp thư viện.'
            return result(hours_answer['answer']+'\n\n'+notice,'needs_confirmation',
                          hours_answer['sources']+([source(room)] if room else []))
        return hours_answer
    if outside_definition(question) or re.search(r'\b(?:viet|tao|sinh) (?:giup (?:toi|minh) )?(?:code|ma nguon|bai van)\b',q):
        return library_redirect(question)
    index_rows = published_rows(state.db)
    if re.search(r'\b(?:doab|doaj)\b',intent_q) and re.search(r'\b(?:dang lai|chia se|dung lai|tai su dung|giay phep|ban quyen)\b',intent_q):
        guide=next((row for row in index_rows if row['category']=='resources'
                    and {'doab','doaj'}<={normalize(word) for word in row['keywords']}
                    and 'giay phep' in normalize(row['answer'])),None)
        if guide:
            status='needs_confirmation' if guide['status']=='needs_confirmation' else 'answered'
            return result(guide['answer'],status,[source(guide)])
        return result('Hãy xem giấy phép đi kèm tài liệu trước khi đăng lại. Mình chưa có hướng dẫn của thư viện để đối chiếu cho nguồn bạn hỏi.','needs_confirmation')
    rows = [row for row in index_rows if row['category'] not in ('hours','hours_reference','hours_contact','interlibrary')]
    loan_item=r'(?:sach|tai lieu|(?:cuon|quyen)(?: sach)? (?:nay|do|ay)|(?:cuon|quyen) sach)'
    lost_book=re.search(r'\b(?:lam |danh )?mat '+loan_item+r'\b',intent_q)
    damaged_book=re.search(r'\b(?:lam )?hong '+loan_item+r'\b',intent_q)
    return_book=re.search(r'\btra '+loan_item+r'\b',intent_q)
    late_return=return_book and re.search(r'\b(?:tre|muon|qua han)\b',intent_q[return_book.end():])
    return_procedure=return_book and re.search(r'\b(?:quay|can lam gi|lam the nao|lam sao|thu tuc|quy trinh|cach tra|tra o dau|co so khac)\b',intent_q)
    return_fee=return_procedure and re.search(r'\b(?:phi|'+PENALTY_WORD+r'|bao nhieu tien)\b',intent_q)
    if lost_book or damaged_book or (return_book and (return_procedure or not re.search(r'\b(phi|'+PENALTY_WORD+r'|han tra|khi nao tra|bao gio tra|tra khi nao|tra bao gio|bao nhieu tien)\b',intent_q))):
        categories=('fees',) if lost_book or damaged_book else ('borrowing_guide','fees') if late_return or return_fee else ('borrowing_guide',)
        references=[source(row) for category in categories if (row:=next((r for r in rows if r['category']==category),None))]
        if lost_book or damaged_book:
            condition='bị mất' if lost_book else 'bị hỏng'
            answer=f'Hãy báo thư viện về tài liệu {condition}. Gửi kèm nhan đề hoặc mã tài liệu nếu có để thủ thư kiểm tra khoản mượn và hướng dẫn cách xử lý, kể cả bồi hoàn nếu áp dụng.'
        else:
            answer='Hãy liên hệ quầy mượn–trả để xác nhận nơi nhận sách rồi mang theo tài liệu cần trả. Sau đó, kiểm tra khoản mượn trong Trang cá nhân OPAC hoặc nhờ thủ thư xác nhận đã ghi trả.'
            if re.search(r'\b(?:co so khac|khac co so)\b',intent_q) or len(requested_campuses(intent_q) or ())>1:
                answer='Mình chưa xác nhận được bạn có thể trả ở cơ sở khác. '+answer
            if late_return or return_fee:
                answer+=' Nếu sách đã quá hạn, hỏi thủ thư cách xử lý và mức phí áp dụng cho khoản mượn của bạn.'
        return result(answer,'needs_confirmation',references)
    if re.search(r'\b(?:mat|quen|khong co) the (?:sinh vien|ban doc|thu vien)\b',intent_q) and re.search(r'\bmuon '+loan_item+r'\b',intent_q):
        guide=next((row for row in rows if row['category']=='borrowing_guide'),None)
        return result('Khi mượn sách, thư viện yêu cầu xuất trình thẻ bạn đọc. Nếu bạn mất hoặc quên thẻ, hãy hỏi thủ thư trước khi đến xem có thể dùng giấy tờ thay thế hay cần cấp lại thẻ.',
                      'needs_confirmation',[source(guide)] if guide else [])
    if re.search(r'\b(phong hoc|phong doc nhom|dat phong|hoc nhom)\b',q) and re.search(r'\b(giu|dat|dang ky)\b',q):
        room=[row for row in rows if row['category']=='support' and re.search(r'\b(dat phong|hoc nhom)\b',normalize(row['question']+' '+row['answer']))]
        if room:
            return result('\n\n'.join(row['answer'] for row in room),'needs_confirmation',[source(row) for row in room])
    if 'dang ky muon' in q and re.search(r'\b(gia han|keo dai han)\b',q):
        renewal=[row for row in rows if row['category']=='renewal']
        if renewal:
            return result('\n\n'.join(row['answer'] for row in renewal),'needs_confirmation',[source(row) for row in renewal])
    procedure=is_borrowing_procedure(question)
    password_help=bool(re.search(r'\bquen mat khau\b',q) and re.search(r'\b(opac|thu vien)\b',q))
    renewal_guide=re.fullmatch(
        r'(?:(?:lam sao de|lam the nao de|cach) |(?:(?:toi|minh|em|ban) )?(?:(?:muon|can|co the|co duoc) )?)'
        r'gia han(?: (?:sach|tai lieu|(?:cuon|quyen)(?: sach)?)(?: dang muon| nay| do| ay)?)?'
        r'(?: them (?:(?:\d{1,3}|mot|hai|ba|vai|may) )?(?:ngay|tuan|thang))?'
        r'(?: (?:(?:thi )?(?:lam sao|lam the nao|nhu the nao)|(?:duoc )?khong))?(?: a)?',q)
    computer_service=bool(re.search(r'\b(?:su dung|dung) may tinh\b',q))
    resources_overview=re.fullmatch(
        r'(?:thu vien(?: uth)?|lic(?: uth)?) (?:co|gioi thieu|cung cap) (?:nhung |cac )?'
        r'co so du lieu dien tu nao(?: cho (?:nguoi doc|ban doc|sinh vien))?(?: a)?',q)
    if guidance:
        rows=[r for r in rows if normalize(r['question'])==normalize(guidance)]
    elif procedure:
        at_desk = re.search(r'\b(?:tai|o|ra|den) quay\b', q)
        if not at_desk and re.search(r'\b(opac|online|truc tuyen|dat cho)\b',q):
            rows=[r for r in rows if r['category'] in ('renewal','opac') and any(normalize(k) in ('dang ky muon','dat cho','dat muon') for k in r['keywords'])]
        else:
            rows=[r for r in rows if r['category']=='borrowing_guide']
    elif computer_service:
        rows=[r for r in rows if r['category']=='computers']
    elif password_help:
        rows=[r for r in rows if r['category']=='support']
    elif renewal_guide:
        rows=[r for r in rows if r['category']=='renewal']
    retrieval_question=guidance or question
    if password_help:
        retrieval_question='Quên mật khẩu OPAC thì làm sao?'
    elif renewal_guide:
        retrieval_question='Tôi muốn gia hạn sách'
    elif resources_overview:
        retrieval_question='Thư viện có những cơ sở dữ liệu điện tử nào?'
    ranked = keyword_search(retrieval_question, rows)
    lexical_ranked=ranked
    if not ranked and not procedure and not library_question(question,history):
        return library_redirect(question)
    if not ranked and not procedure and not library_subject(question):
        return result('Bạn đang hỏi tiếp về dịch vụ thư viện nào, ở cơ sở và ngày nào? Mình cần thông tin cụ thể để đối chiếu nguồn, chưa thể xác nhận từ câu hỏi ngắn này.', 'clarify',suggestions=SUGGESTIONS)
    asks_fee = bool(re.search(r'\b(phi|'+PENALTY_WORD+r'|qua han|tre han|nop (?:chinh xac )?bao nhieu tien)\b',q))
    asks_loan_term = bool(re.search(r'\b(thoi han|han tra|thoi gian muon|muon bao lau|bao nhieu ngay|giu sach.*may ngay)\b',q))
    if procedure:
        asks_loan_term = asks_loan_term or asks_return_date or bool(re.search(r'\bbao lau\b', q))
    asks_renewal = bool(re.search(r'\b(?:(?:co|duoc) gia han|gia han (?:duoc |toi da )?(?:may lan|bao nhieu|bao lau))\b',q))
    policy_query = asks_fee or asks_loan_term or bool(re.search(r'\b(mo cua|dong cua)\b',q))
    if asks_fee and asks_loan_term:
        uncertain=[row for row in rows if row['status']=='needs_confirmation' and (row['category']=='fees' or row['category']=='policy' and re.search(r'\b(muon|han tra)\b',normalize(row['question']+' '+row['answer'])))]
        if uncertain:
            return result('\n\n'.join(row['answer'] for row in uncertain),'needs_confirmation',[source(row) for row in uncertain])
    sensitive = bool(guidance) or procedure or computer_service or policy_query or bool(re.search(r'\b(gia han|mat khau)\b',q))
    vectors=state.vectors if os.getenv('ENABLE_VECTORS','true').lower()=='true' and not state.settings.testing and not sensitive else None
    if (procedure or computer_service) and len(rows)==1:
        # A reviewed service category is stronger than shared words about books/accounts.
        retrieval={'ranked':[(rows[0],1)],'method':'keyword'}
    else:
        if vectors is None:
            retrieval=retrieve_knowledge(retrieval_question,rows)
        else:
            retrieval=retrieve_knowledge(retrieval_question,rows,vectors,index_rows=index_rows)
    ranked=retrieval['ranked']
    semantic=retrieval['method'] in ('hybrid','semantic')
    if not ranked:
        return result('Mình chưa tìm được thông tin đủ căn cứ cho câu hỏi này. Bạn có thể hỏi rõ tên dịch vụ, cơ sở hoặc cách tra cứu cần hỗ trợ.', 'not_found',suggestions=SUGGESTIONS)
    top, score = ranked[0]
    if policy_query and not procedure and not (top['status']=='verified' and top.get('verified_by') and top.get('valid_from') and top.get('valid_until')):
        return result('Mình chưa có thông tin hiện hành đã được thư viện xác nhận cho nội dung này. Vui lòng xác nhận với thư viện trước khi áp dụng lịch, phí hoặc thời hạn; mình không tự suy ra từ tài liệu cũ.',
                      'needs_confirmation',[source(top)])
    # Cosine similarity and lexical intent scores have different scales.
    ambiguity_ranked=lexical_ranked if semantic and lexical_ranked and lexical_ranked[0][0]['id']==top['id'] else ranked
    if len(ambiguity_ranked)>1 and ambiguity_ranked[0][1]<1 and ambiguity_ranked[1][1]>=ambiguity_ranked[0][1]-0.08 and ambiguity_ranked[1][0]['category']!=top['category']:
        combined=[row for row,_ in ranked[:2]]
        if not sensitive and (question.count('?')>=2 or re.search(r'\b(dong thoi|va neu|va neu muon)\b',q)) and all(row['status'] in ('reviewed_public','verified') and row['category'] not in ('hours','hours_reference','fees','policy','renewal') for row in combined):
            return result('\n\n'.join(row['answer'] for row in combined),sources=[source(row) for row in combined])
        return result('Có nhiều nội dung có thể liên quan. Bạn chọn câu hỏi gần nhất hoặc hỏi riêng từng ý nhé.', 'clarify', suggestions=[r['question'] for r,_ in ranked[:3]])
    unconfirmed = top['status']=='needs_confirmation'
    if top['category'] in ('hours','fees','policy') and top['status']!='verified':
        unconfirmed = True
    if semantic and sensitive and top['category'] not in ('hours','fees','policy','renewal','support'):
        return result('Chưa tìm được nguồn nghiệp vụ phù hợp để xác nhận. Hãy liên hệ thư viện hoặc hỏi cụ thể hơn.', 'needs_confirmation',suggestions=SUGGESTIONS)
    answer, selected, mode = top['answer'], [top], 'faq'
    if not unconfirmed and top['category']=='support' and 'mat khau' in q and re.search(r'\b(lien he|ben nao|ho tro|email)\b',q):
        contacts=[row for row,_ in keyword_search('Liên hệ thư viện để được hỗ trợ ở đâu?',rows)
                  if row['id']!=top['id'] and row['category']=='support' and row['status'] in ('reviewed_public','verified')][:1]
        for row in contacts:
            answer+='\n\n'+row['answer']
            selected.append(row)
    branches = set(re.findall(r'\b(?:co so|cs)\s*(\d+)\b', intent_q))
    duration = re.search(r'\b(?:trong|khoang) (\d{1,2}) ngay\b', intent_q)
    if procedure and top['category']=='borrowing_guide' and not unconfirmed and (branches or duration):
        answer = re.sub(r'(?<=[.!?])\s+(?=[A-ZÀ-ỸĐ])', '\n\n', answer)
        if not state.settings.testing and provider_name()=='ollama':
            formatted = format_borrowing_guide(top['answer'])
            if formatted:
                answer, mode = formatted, 'rag'
            else:
                mode = 'fallback'
        location = f' tại cơ sở {next(iter(branches))}' if len(branches)==1 and branches <= {'1','2','3'} else ''
        if duration:
            confirmation = f'Bạn muốn mang sách về trong {duration[1]} ngày{location}. Khi làm thủ tục, hãy hỏi thủ thư cuốn đó có được mượn về không và kiểm tra ngày trả được ghi nhận trước khi rời quầy.'
        else:
            confirmation = f'Với yêu cầu mượn{location}, hãy kiểm tra tài liệu thuộc kho nào trên OPAC và hỏi thủ thư tại quầy về điều kiện mượn về.'
        answer += '\n\n' + confirmation + ' Mình chưa có căn cứ để xác nhận điều kiện áp dụng cho cuốn bạn định mượn.'
        unconfirmed = True
    elif not unconfirmed and not sensitive and not state.settings.testing and (semantic or score<0.85):
        candidates = [r for r,_ in ranked[:3] if r['status']!='needs_confirmation' and r['category'] not in ('hours','fees','policy')]
        candidate_ids={row['id'] for row in candidates}
        evidence=[excerpt for excerpt in retrieval['evidence'] if excerpt['source_id'] in candidate_ids]
        generated = generate_answer(question,candidates,history,evidence=evidence)
        if generated:
            answer, mode = generated['answer'], 'rag'
            selected = [r for r in candidates if r['id'] in generated['source_ids']]
        elif provider_name()!='none':
            mode = 'fallback'
    if procedure:
        confirmations = []
        if asks_fee:
            confirmations.append('Mình chưa xác nhận được mức phí hiện hành. Hãy hỏi thư viện trước khi áp dụng hoặc thanh toán.')
        if asks_loan_term:
            confirmations.append('Hạn trả của cuốn bạn mượn cần xác nhận tại quầy hoặc xem trong Trang cá nhân trên OPAC sau khi ghi mượn.')
        if asks_renewal:
            confirmations.append('Điều kiện và số lần gia hạn cần xác nhận với thư viện theo khoản mượn của bạn.')
        if confirmations:
            answer += '\n\n' + '\n'.join(confirmations)
            unconfirmed = True
    current = {r['id']:r for r in published_rows(state.db)}
    if any(current.get(r['id'])!=r for r in selected):
        return result('Nguồn vừa thay đổi hoặc không còn hiệu lực trong khi xử lý. Vui lòng hỏi lại để dùng dữ liệu mới nhất.', 'needs_confirmation',suggestions=SUGGESTIONS)
    suggestions = None
    if guidance=='Hướng dẫn tra cứu OPAC' and not unconfirmed:
        examples='\n'.join(f'• Theo {field.lower()}, hãy thử “{example}”.' for field,example in CATALOG_SEARCH_EXAMPLES)
        chat_guide=('Tìm ngay trong chatbot\nNhập nhan đề, tên tác giả hoặc chủ đề vào ô chat rồi gửi.\n'
                    +examples+'\n\nMở nhan đề trong kết quả để xem biểu ghi gốc. Bạn có thể hỏi tiếp “Cuốn thứ nhất xuất bản năm nào?”. '
                    'Nếu chưa thấy tài liệu, thử rút ngắn nhan đề hoặc tìm theo tác giả.')
        opac_guide='Tra cứu trên OPAC\n'+answer
        sections=(opac_guide,chat_guide) if 'opac' in intent_q.split() and 'chatbot' not in intent_q.split() else (chat_guide,opac_guide)
        answer='\n\n'.join(sections)
        suggestions=[example for _,example in CATALOG_SEARCH_EXAMPLES]
    return result(answer, 'needs_confirmation' if unconfirmed else 'answered',[source(r) for r in selected],suggestions=suggestions,mode=mode)
