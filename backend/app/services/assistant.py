import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from .knowledge import published_rows, today
from .rag_service import keyword_search, normalize
from .llm_service import generate_answer, provider_name
from .catalog import contextual_question,is_book_request,book_query,search_books
from urllib.parse import urlencode

SUGGESTIONS = ['Hướng dẫn tra cứu OPAC','Thư viện mở cửa lúc mấy giờ hôm nay?','Tôi muốn gia hạn sách']


def source(row):
    return {'title':row['source_title'], 'url':row['source_url'], 'checked_at':row['checked_at']}


def result(answer,status='answered',sources=None,suggestions=None,mode='faq'):
    return {'answer':answer,'status':status,'sources':sources or [],'suggestions':suggestions or [],'mode':mode}


def answer_question(state, question, history=None):
    original_q=normalize(question)
    question=contextual_question(question,history)
    q = normalize(question)
    if q in ('xin chao','chao','hello','hi'):
        return result('Chào bạn! Mình có thể hỗ trợ tra cứu OPAC, hướng dẫn tài nguyên điện tử và thông tin dịch vụ thư viện.',suggestions=SUGGESTIONS)
    if is_book_request(question):
        query=book_query(question)
        if query:
            books=search_books(state,query)[:5]
            if books:
                answer=f'Mình tìm được {len(books)} biểu ghi phù hợp trong danh mục đã rà soát. Xem tên sách, nguồn và ngày kiểm tra bên dưới. Đây là bản chụp metadata; để biết còn sách hoặc hạn mượn, hãy kiểm tra trực tiếp OPAC.'
                status='answered'
                if history and re.search(r'\b(cuon do|cuon nay|sach do|sach nay)\b',original_q):
                    if re.search(r'\b(con ban|con sach|co san|con khong|tinh trang)\b',original_q):
                        answer='Metadata đang có không xác nhận tình trạng còn bản sách theo thời gian thực. Hãy mở biểu ghi OPAC gốc bên dưới hoặc hỏi thư viện trước khi đến mượn.'
                        status='needs_confirmation'
                    elif len(books)>1:
                        return {**result('Có nhiều tài liệu trong ngữ cảnh. Bạn vui lòng chọn nhan đề cụ thể.','clarify',suggestions=['Tìm sách '+b['title'] for b in books[:3]]),'books':books,'context_query':query}
                    elif 'tac gia' in original_q:
                        answer=f"Theo biểu ghi nguồn, tác giả của “{books[0]['title']}” là {books[0]['author']}." if books[0]['author'] else 'Biểu ghi chưa có thông tin tác giả; mình không tự suy đoán.'
                    elif re.search(r'\b(xuat ban|nam nao)\b',original_q):
                        answer=f"Biểu ghi “{books[0]['title']}” ghi năm xuất bản {books[0]['year']}." if books[0]['year'] else 'Biểu ghi chưa có năm xuất bản; hãy kiểm tra nguồn gốc.'
                return {**result(answer,status,sources=[{'title':b['title'],'url':b['url'],'checked_at':b['checked_at']} for b in books]),'books':books,'context_query':query}
            url='https://opacthuvien.ut.edu.vn/opac/Oshow.aspx?'+urlencode({'rdSearchOption':0,'txtSearch':query})
            return {**result('Chưa có biểu ghi phù hợp trong danh mục đã rà soát của chatbot. Điều này không chứng minh thư viện không có sách. Bạn có thể tìm tiếp trên OPAC hoặc nhập tên/tác giả cụ thể hơn.',
                            'not_found',sources=[{'title':'Tìm trực tiếp trên OPAC','url':url,'checked_at':None}]),'books':[],'context_query':query}
    if re.search(r'\b(gio|mo cua|dong cua|lich phuc vu|hom nay)\b',q) and any(x in q for x in ('gio','mo cua','dong cua','phuc vu')):
        branch = re.search(r'(?:co so|cs)\s*([123])',q)
        if not branch:
            return result('Bạn muốn xem giờ phục vụ tại cơ sở nào? Vui lòng hỏi kèm cơ sở và ngày cần tra cứu.', 'clarify', suggestions=[f'Giờ mở cửa hôm nay cơ sở {i}' for i in (1,2,3)])
        now = datetime.now(ZoneInfo('Asia/Ho_Chi_Minh'))
        if 'hom nay' not in q:
            return result('Hiện mình tra lịch theo ngày hôm nay. Hãy hỏi “Giờ mở cửa hôm nay” kèm cơ sở để đối chiếu lịch đã xác nhận.', 'clarify', suggestions=[f'Giờ mở cửa hôm nay cơ sở {branch[1]}'])
        with state.db() as db:
            rows = db.execute('SELECT * FROM schedules WHERE branch=? AND weekday=? AND valid_from<=? AND valid_until>=?',
                              (branch[1],now.weekday(),now.date().isoformat(),now.date().isoformat())).fetchall()
        if rows:
            # A short dated exception overrides the broader weekly schedule.
            span = min((datetime.fromisoformat(r['valid_until'])-datetime.fromisoformat(r['valid_from'])).days for r in rows)
            rows = [r for r in rows if (datetime.fromisoformat(r['valid_until'])-datetime.fromisoformat(r['valid_from'])).days==span]
            windows = 'Nghỉ phục vụ' if any(r['closed'] for r in rows) else '; '.join(f"{r['opens']}–{r['closes']}" for r in rows)
            notes = ' '.join(r['note'] for r in rows if r['note'])
            return result(f"Lịch đã xác nhận cho cơ sở {branch[1]} ngày {now:%d/%m/%Y}: {windows}. {notes}".strip(),
                          sources=[{'title':r['source_title'],'url':r['source_url'],'checked_at':r['checked_at']} for r in rows])
    rows = published_rows(state.db)
    ranked = keyword_search(question, rows)
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
