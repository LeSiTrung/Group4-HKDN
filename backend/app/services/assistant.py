import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from .knowledge import published_rows, today
from .rag_service import keyword_search, normalize
from .llm_service import generate_answer, provider_name, MAX_MODEL_MESSAGE_CHARS
from .catalog import contextual_question,is_book_request,book_query,search_books,book_attribute,book_followup
from urllib.parse import urlencode

SUGGESTIONS = ['Hướng dẫn tra cứu OPAC','Thư viện mở cửa lúc mấy giờ hôm nay?','Tôi muốn gia hạn sách']


def source(row):
    return {'title':row['source_title'], 'url':row['source_url'], 'checked_at':row['checked_at']}


def result(answer,status='answered',sources=None,suggestions=None,mode='faq'):
    return {'answer':answer,'status':status,'sources':sources or [],'suggestions':suggestions or [],'mode':mode}


def library_subject(question):
    return bool(re.search(r'\b(thu vien|opac|uth|lic|sach|tai lieu|gia han|qua han|han tra|muon tra|mo cua|dong cua|gio phuc vu|lich phuc vu|proquest|stinet|xep gia|isbn|ddc|ebook)\b',normalize(question)))


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


def answer_question(state, question, history=None):
    if len(question)>MAX_MODEL_MESSAGE_CHARS:
        return result('Mình đã nhận đầy đủ tin nhắn, nhưng nội dung vượt khả năng đọc trong một lượt của mô hình đang dùng. Bạn hãy chia thành các phần nhỏ hơn hoặc gửi riêng câu hỏi và đoạn cần hỗ trợ. Mình không âm thầm cắt nội dung để trả lời như đã đọc hết.', 'clarify')
    original_q=normalize(question)
    question=contextual_question(question,history)
    if len(question)>MAX_MODEL_MESSAGE_CHARS:
        return result('Ngữ cảnh tài liệu trước quá dài cho một lượt xử lý. Bạn hãy gửi lại tên/chủ đề sách ngắn gọn hoặc chia nội dung thành các phần; mình không âm thầm cắt ngữ cảnh để tìm kiếm.', 'clarify')
    q = normalize(question)
    if q==original_q and book_followup(original_q) and book_attribute(original_q):
        return result('Bạn đang hỏi về tài liệu nào? Vui lòng cung cấp nhan đề hoặc tìm sách trước để mình đối chiếu đúng biểu ghi.', 'clarify',suggestions=['Tìm sách Olympic cơ học'])
    if 'muon sach' in q and re.search(r'\b(bao gio|khi nao)\b.*\btra\b',q):
        question='Thời hạn mượn sách'
        q=normalize(question)
    if re.fullmatch(r'(xin chao|chao|hello|hi|alo)( ban| thu vien| tro ly)?',q):
        return result('Chào bạn! Mình có thể hỗ trợ tra cứu OPAC, hướng dẫn tài nguyên điện tử và thông tin dịch vụ thư viện.',suggestions=SUGGESTIONS)
    if q in ('cam on','cam on ban','thank you','thanks','ok'):
        return result('Rất vui được hỗ trợ bạn. Khi cần tìm tài liệu hoặc hỏi về dịch vụ thư viện, bạn cứ nhắn mình nhé.',suggestions=SUGGESTIONS)
    if is_book_request(question):
        if re.search(r'\b(khong phai|ngoai tru|loai tru|mo cua|gio phuc vu|gia han|phi|phat|qua han|han tra)\b',q):
            return result('Câu hỏi có điều kiện loại trừ hoặc nhiều yêu cầu khác nhau. Bạn vui lòng hỏi riêng tên/chủ đề sách cần tìm, sau đó hỏi về dịch vụ để mình đối chiếu đúng từng nguồn.', 'clarify',suggestions=SUGGESTIONS)
        query=book_query(question)
        if query:
            books=search_books(state,query)[:5]
            if books:
                answer=f'Mình tìm được {len(books)} biểu ghi phù hợp trong danh mục đã rà soát. Xem tên sách, nguồn và ngày kiểm tra bên dưới. Đây là bản chụp metadata; để biết còn sách hoặc hạn mượn, hãy kiểm tra trực tiếp OPAC.'
                status='answered'
                attribute=book_attribute(original_q)
                if attribute=='availability':
                    answer='Metadata đang có không xác nhận tình trạng còn bản sách theo thời gian thực. Hãy mở biểu ghi OPAC gốc bên dưới hoặc hỏi thư viện trước khi đến mượn.'
                    status='needs_confirmation'
                elif history and book_followup(original_q) and attribute:
                    if len(books)>1:
                        return {**result('Có nhiều tài liệu trong ngữ cảnh. Bạn vui lòng chọn nhan đề cụ thể.','clarify',suggestions=['Tìm sách '+b['title'] for b in books[:3]]),'books':books,'context_query':query}
                    if attribute in ('author','year') and books[0][attribute].strip():
                        label='tác giả' if attribute=='author' else 'năm xuất bản'
                        answer=f"Theo biểu ghi nguồn, {label} của “{books[0]['title']}” là {books[0][attribute]}."
                    else:
                        label={'isbn':'ISBN','shelf':'vị trí kệ / ký hiệu xếp giá','publisher':'nhà xuất bản','author':'tác giả','year':'năm xuất bản'}[attribute]
                        answer=f'Biểu ghi đang có chưa xác nhận {label}. Bạn hãy mở nguồn gốc hoặc hỏi thư viện; mình không tự suy đoán thông tin này.'
                        status='needs_confirmation'
                return {**result(answer,status,sources=[{'title':b['title'],'url':b['url'],'checked_at':b['checked_at']} for b in books]),'books':books,'context_query':query}
            url='https://opacthuvien.ut.edu.vn/opac/Oshow.aspx?'+urlencode({'rdSearchOption':0,'txtSearch':query})
            return {**result('Chưa có biểu ghi phù hợp trong danh mục đã rà soát của chatbot. Điều này không chứng minh thư viện không có sách. Bạn có thể tìm tiếp trên OPAC hoặc nhập tên/tác giả cụ thể hơn.',
                            'not_found',sources=[{'title':'Tìm trực tiếp trên OPAC','url':url,'checked_at':None}]),'books':[],'context_query':query}
    if re.search(r'\b(mo cua|dong cua|lich phuc vu|gio phuc vu|thoi gian phuc vu)\b',q):
        branches=set(re.findall(r'\b(?:co so|cs)\s*(\d+)\b',q))
        if len(branches)!=1 or not branches<={'1','2','3'}:
            return result('Bạn muốn xem giờ phục vụ tại cơ sở nào? Vui lòng hỏi kèm cơ sở và ngày cần tra cứu.', 'clarify', suggestions=[f'Giờ mở cửa hôm nay cơ sở {i}' for i in (1,2,3)])
        branch=next(iter(branches))
        now = datetime.now(ZoneInfo('Asia/Ho_Chi_Minh'))
        if 'hom nay' not in q or re.search(r'\b(mai|ngay mot|ngay kia|hom qua|tuan sau|tuan truoc|ngay \d+|thang \d+|thu hai|thu ba|thu tu|thu nam|thu sau|thu bay|chu nhat)\b',q) or re.search(r'\b\d{1,2}[/-]\d{1,2}\b',question):
            return result('Hiện mình tra lịch theo ngày hôm nay. Hãy hỏi “Giờ mở cửa hôm nay” kèm một cơ sở; mình chưa áp dụng lịch hôm nay cho ngày khác.', 'clarify', suggestions=[f'Giờ mở cửa hôm nay cơ sở {branch}'])
        with state.db() as db:
            rows = db.execute('SELECT * FROM schedules WHERE branch=? AND weekday=? AND valid_from<=? AND valid_until>=?',
                              (branch,now.weekday(),now.date().isoformat(),now.date().isoformat())).fetchall()
        if rows:
            # A short dated exception overrides the broader weekly schedule.
            span = min((datetime.fromisoformat(r['valid_until'])-datetime.fromisoformat(r['valid_from'])).days for r in rows)
            rows = [r for r in rows if (datetime.fromisoformat(r['valid_until'])-datetime.fromisoformat(r['valid_from'])).days==span]
            windows = 'Nghỉ phục vụ' if any(r['closed'] for r in rows) else '; '.join(f"{r['opens']}–{r['closes']}" for r in rows)
            notes = ' '.join(r['note'] for r in rows if r['note'])
            return result(f"Lịch đã xác nhận cho cơ sở {branch} ngày {now:%d/%m/%Y}: {windows}. {notes}".strip(),
                          sources=[{'title':r['source_title'],'url':r['source_url'],'checked_at':r['checked_at']} for r in rows])
    if outside_definition(question):
        return library_redirect(question)
    rows = published_rows(state.db)
    ranked = keyword_search(question, rows)
    if not ranked and not library_question(question,history):
        return library_redirect(question)
    if not ranked and not library_subject(question):
        return result('Bạn đang hỏi tiếp về dịch vụ thư viện nào, ở cơ sở và ngày nào? Mình cần thông tin cụ thể để đối chiếu nguồn, chưa thể xác nhận từ câu hỏi ngắn này.', 'clarify',suggestions=SUGGESTIONS)
    semantic = False
    if not ranked and os.getenv('ENABLE_VECTORS','true').lower()=='true' and not state.settings.testing:
        try:
            ranked = state.vectors.search(question,rows)
            semantic = bool(ranked)
        except Exception:
            # Provider details stay in admin health, never in public chat.
            pass
    if not ranked:
        return result('Mình chưa tìm được thông tin đủ căn cứ cho câu hỏi này. Bạn có thể hỏi rõ tên dịch vụ, cơ sở hoặc cách tra cứu cần hỗ trợ.', 'not_found',suggestions=SUGGESTIONS)
    top, score = ranked[0]
    policy_query = bool(re.search(r'\b(phi|phat|qua han|thoi han|thoi gian muon|muon bao lau|bao nhieu ngay|mo cua|dong cua)\b',q))
    if policy_query and not (top['status']=='verified' and top.get('verified_by') and top.get('valid_from') and top.get('valid_until')):
        return result('Mình chưa có thông tin hiện hành đã được thư viện xác nhận cho nội dung này. Vui lòng xác nhận với thư viện trước khi áp dụng lịch, phí hoặc thời hạn; mình không tự suy ra từ tài liệu cũ.',
                      'needs_confirmation',[source(top)])
    if len(ranked)>1 and score<1 and ranked[1][1]>=score-0.08 and ranked[1][0]['category']!=top['category']:
        return result('Có nhiều nội dung có thể liên quan. Bạn chọn câu hỏi gần nhất hoặc hỏi riêng từng ý nhé.', 'clarify', suggestions=[r['question'] for r,_ in ranked[:3]])
    unconfirmed = top['status']=='needs_confirmation'
    sensitive = any(x in q for x in ('gia han','phi','phat','thoi han','mo cua','qua han','mat khau'))
    if top['category'] in ('hours','fees','policy') and top['status']!='verified':
        unconfirmed = True
    if semantic and sensitive and top['category'] not in ('hours','fees','policy','renewal','support'):
        return result('Chưa tìm được nguồn nghiệp vụ phù hợp để xác nhận. Hãy liên hệ thư viện hoặc hỏi cụ thể hơn.', 'needs_confirmation',suggestions=SUGGESTIONS)
    answer, selected, mode = top['answer'], [top], 'faq'
    if not unconfirmed and not sensitive and not state.settings.testing and (semantic or score<0.85):
        candidates = [r for r,_ in ranked[:3] if r['status']!='needs_confirmation' and r['category'] not in ('hours','fees','policy')]
        generated = generate_answer(question,candidates,history)
        if generated:
            answer, mode = generated['answer'], 'rag'
            selected = [r for r in candidates if r['id'] in generated['source_ids']]
        elif provider_name()!='none':
            mode = 'fallback'
    current = {r['id']:r for r in published_rows(state.db)}
    if any(current.get(r['id'])!=r for r in selected):
        return result('Nguồn vừa thay đổi hoặc không còn hiệu lực trong khi xử lý. Vui lòng hỏi lại để dùng dữ liệu mới nhất.', 'needs_confirmation',suggestions=SUGGESTIONS)
    return result(answer, 'needs_confirmation' if unconfirmed else 'answered',[source(r) for r in selected],mode=mode)
