import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from .knowledge import published_rows, today
from .rag_service import keyword_search, normalize
from .retrieval import retrieve_knowledge
from .llm_service import format_borrowing_guide, generate_answer, provider_name, MAX_MODEL_MESSAGE_CHARS
from .catalog import contextual_question,is_book_request,is_borrowing_procedure,search_guidance,unquoted_text,book_query,search_books,book_attribute,book_followup,selected_title,author_query,structured_book_query,PENALTY_WORD
from urllib.parse import urlencode
from .opac_availability import get_availability
from .recommendations import is_recommendation_request, recommend_books

SUGGESTIONS = ['Hướng dẫn tra cứu OPAC','Thư viện mở cửa lúc mấy giờ hôm nay?','Tôi muốn gia hạn sách']


def source(row):
    return {'title':row['source_title'], 'url':row['source_url'], 'checked_at':row['checked_at']}


def result(answer,status='answered',sources=None,suggestions=None,mode='faq'):
    return {'answer':answer,'status':status,'sources':sources or [],'suggestions':suggestions or [],'mode':mode}


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


def answer_question(state, question, history=None):
    if len(question)>MAX_MODEL_MESSAGE_CHARS:
        return result('Mình đã nhận đầy đủ tin nhắn, nhưng nội dung vượt khả năng đọc trong một lượt của mô hình đang dùng. Bạn hãy chia thành các phần nhỏ hơn hoặc gửi riêng câu hỏi và đoạn cần hỗ trợ. Mình không âm thầm cắt nội dung để trả lời như đã đọc hết.', 'clarify')
    original_q=normalize(question)
    intent_q=normalize(unquoted_text(question))
    for conjunction in re.finditer(r'\b(?:va|dong thoi|sau do)\b',intent_q):
        before,after=intent_q[:conjunction.start()].strip(),intent_q[conjunction.end():].strip()
        if (search_guidance(before) and is_book_request(after)) or (is_book_request(before) and re.match(r'^(?:huong dan|cach|lam the nao|lam sao)\b',after) and search_guidance(after)):
            return result('Bạn muốn tìm tài liệu cụ thể và hỏi cách tra cứu. Hãy gửi riêng từng yêu cầu để mình trả đúng sách và đúng hướng dẫn.', 'clarify',suggestions=SUGGESTIONS)
    question=contextual_question(question,history)
    guidance=search_guidance(question)
    # Natural borrowing requests may also ask for instructions in the same turn.
    borrowing=bool(re.search(r'\b(muon|roi|tinh trang|so ban)\b',intent_q))
    natural=re.search(r'\bco (?:nhung )?(?:sach|tai lieu) (.+?) (?:nao\b|co the\b|dang roi\b|con roi\b)',original_q) if borrowing and not guidance else None
    if natural:
        question='Tìm sách '+natural[1]
    if len(question)>MAX_MODEL_MESSAGE_CHARS:
        return result('Ngữ cảnh tài liệu trước quá dài cho một lượt xử lý. Bạn hãy gửi lại tên/chủ đề sách ngắn gọn hoặc chia nội dung thành các phần; mình không âm thầm cắt ngữ cảnh để tìm kiếm.', 'clarify')
    q = normalize(question)
    if q==original_q and book_followup(original_q) and book_attribute(original_q):
        return result('Bạn đang hỏi về tài liệu nào? Vui lòng cung cấp nhan đề hoặc tìm sách trước để mình đối chiếu đúng biểu ghi.', 'clarify',suggestions=['Tìm sách Olympic cơ học'])
    asks_return_date = bool(re.search(r'\b(?:bao gio|khi nao) (?:\w+ ){0,3}tra\b', intent_q))
    if 'muon sach' in intent_q and asks_return_date and not is_borrowing_procedure(question):
        question='Thời hạn mượn sách'
        q=normalize(question)
    if re.fullmatch(r'(xin chao|chao|hello|hi|alo)( ban| thu vien| tro ly)?',q):
        return result('Chào bạn! Mình có thể hỗ trợ tra cứu OPAC, hướng dẫn tài nguyên điện tử và thông tin dịch vụ thư viện.',suggestions=SUGGESTIONS)
    if q in ('cam on','cam on ban','thank you','thanks','ok'):
        return result('Rất vui được hỗ trợ bạn. Khi cần tìm tài liệu hoặc hỏi về dịch vụ thư viện, bạn cứ nhắn mình nhé.',suggestions=SUGGESTIONS)
    if is_book_request(question):
        if re.search(r'\b(khong phai|ngoai tru|loai tru|dung lay|khong can|bo qua|mo cua|gio phuc vu|gia han|phi|'+PENALTY_WORD+r'|qua han|han tra|thoi han|thoi gian muon|muon bao lau|bao nhieu ngay)\b',intent_q) or (natural and re.search(r'\bva (?:sach|tai lieu)\b',intent_q)):
            return result('Câu hỏi có điều kiện loại trừ hoặc nhiều yêu cầu khác nhau. Bạn vui lòng hỏi riêng tên/chủ đề sách cần tìm, sau đó hỏi về dịch vụ để mình đối chiếu đúng từng nguồn.', 'clarify',suggestions=SUGGESTIONS)
        query=book_query(question)
        if len(query)>200:
            return result('Từ khóa tra cứu quá dài để đối chiếu danh mục trong một lượt. Bạn hãy gửi tên tài liệu, tác giả hoặc chủ đề ngắn hơn; tin nhắn đã nhận không bị cắt để tìm kiếm.', 'clarify')
        if not query:
            return result('Bạn muốn tìm sách về chủ đề hoặc kỹ năng nào? Cho mình biết tên tài liệu, tác giả hoặc nhu cầu học tập để mình chọn đúng tài liệu.', 'clarify')
        if query:
            recommendation=None
            structured=structured_book_query(question)
            if structured:
                books=search_books(state,query,field=structured[0])
            elif is_recommendation_request(question) and not author_query(question) and book_attribute(intent_q) in (None,'availability'):
                recommendation=recommend_books(state,question)
                books=recommendation['books']
                query=recommendation['query']
                if not query:
                    return result('Bạn muốn tìm sách về chủ đề hoặc kỹ năng nào? Cho mình biết ngành học và mục tiêu, mình sẽ gợi ý tài liệu có trong danh mục thư viện.', 'clarify')
                question='Tìm sách '+query
                if history and re.fullmatch(r'(?:co cuon nao )?(?:danh cho )?(?:nguoi moi(?: bat dau)?|nang cao)(?: khong)?',original_q):
                    question=contextual_question('Tác giả',history)
            elif author_query(question):
                books=search_books(state,query,field='author')
                selection=selected_title([{'role':'user','content':question}])
                titles=[b for b in search_books(state,selection,field='title') if normalize(b['title'])==selection] if selection else []
                if books and titles:
                    choices=list({b['id']:b for b in titles+books}.values())[:5]
                    return {**result('Cụm từ có thể là nhan đề hoặc tên tác giả. Bạn hãy mở Tra cứu tài liệu và chọn “Nhan đề” hoặc “Tác giả” để xác định.','clarify'),
                            'books':choices,'context_query':question}
                books=titles or books
            else:
                books=search_books(state,query)
            attribute=book_attribute(intent_q)
            if history and book_followup(original_q) and attribute:
                selection=selected_title(history)
                exact=[b for b in books if normalize(b['title'])==selection]
                if exact:
                    books=exact
            books=books[:5]
            if books:
                answer=f'Mình tìm được {len(books)} tài liệu phù hợp. Bạn có thể xem thông tin và mở nguồn thư viện bên dưới; tình trạng còn sách và quyền truy cập có thể thay đổi.'
                status='answered'
                if recommendation:
                    answer='Mình gợi ý các tài liệu dưới đây theo nhu cầu học tập của bạn. Mỗi cuốn có lý do lựa chọn từ nhan đề hoặc từ khóa của biểu ghi; bạn có thể mở nguồn để xem nội dung trước khi chọn.'
                    if recommendation['level_unconfirmed']:
                        answer+=' Thông tin hiện có chưa xác nhận mức độ bạn yêu cầu. Đây là các tài liệu cùng chủ đề; bạn nên xem mô tả để chọn cuốn phù hợp với kiến thức nền.'
                        status='clarify'
                    elif not recommendation['level']:
                        answer+=' Bạn đang muốn học mảng nào và đã có kiến thức nền đến đâu để mình chọn sát hơn?'
                if attribute=='availability' or (borrowing and natural):
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
                elif history and book_followup(original_q) and attribute:
                    if len(books)>1:
                        return {**result('Có nhiều tài liệu trong ngữ cảnh. Bạn vui lòng chọn nhan đề cụ thể.','clarify',suggestions=['Tìm sách '+b['title'] for b in books[:3]]),'books':books,'context_query':question}
                    if attribute in ('author','year') and books[0][attribute].strip():
                        label='tác giả' if attribute=='author' else 'năm xuất bản'
                        answer=f"Theo biểu ghi nguồn, {label} của “{books[0]['title']}” là {books[0][attribute]}."
                    else:
                        label={'isbn':'ISBN','shelf':'vị trí kệ / ký hiệu xếp giá','publisher':'nhà xuất bản','author':'tác giả','year':'năm xuất bản'}[attribute]
                        answer=f'Biểu ghi đang có chưa xác nhận {label}. Bạn hãy mở nguồn gốc hoặc hỏi thư viện; mình không tự suy đoán thông tin này.'
                        status='needs_confirmation'
                return {**result(answer,status,sources=[{'title':b['title'],'url':b['url'],'checked_at':b['checked_at']} for b in books],
                                 suggestions=['Tìm sách '+b['title'] for b in books[:3]] if recommendation else [],
                                 mode='catalog_ai' if recommendation and recommendation['used_model'] else 'catalog'),
                        'books':books,'context_query':question}
            url='https://opacthuvien.ut.edu.vn/opac/Oshow.aspx?'+urlencode({'rdSearchOption':0,'txtSearch':query})
            return {**result('Chưa có biểu ghi phù hợp trong danh mục đã rà soát của chatbot. Điều này không chứng minh thư viện không có sách. Bạn có thể tìm tiếp trên OPAC hoặc nhập tên/tác giả cụ thể hơn.',
                            'not_found',sources=[{'title':'Tìm trực tiếp trên OPAC','url':url,'checked_at':None}]),'books':[],'context_query':question}
    if re.search(r'\b(mo cua|dong cua|lich phuc vu|gio phuc vu|thoi gian phuc vu)\b',q):
        branches=set(re.findall(r'\b(?:co so|cs)\s*(\d+)\b',q))
        if branches and (len(branches)!=1 or not branches<={'1','2','3'}):
            return result('Bạn muốn xem giờ phục vụ tại cơ sở nào? Vui lòng hỏi kèm cơ sở và ngày cần tra cứu.', 'clarify', suggestions=[f'Giờ mở cửa hôm nay cơ sở {i}' for i in (1,2,3)])
        if re.search(r'\b(mai|ngay mot|ngay kia|hom qua|tuan sau|tuan truoc|ngay le|nghi le|tet|ngay \d+|thang \d+|thu hai|thu ba|thu tu|thu nam|thu sau|thu bay|chu nhat)\b',q) or re.search(r'\b\d{1,2}[/-]\d{1,2}\b',question):
            return result('Mình chưa xác nhận lịch theo ngày hoặc ngày lễ bạn hỏi. Bạn có thể xem lịch thường lệ để tham khảo hoặc hỏi “Giờ mở cửa hôm nay” kèm một cơ sở.', 'clarify', suggestions=['Giờ mở cửa thường lệ của thư viện'])
        references=[row for row in published_rows(state.db) if row['category']=='hours_reference']
        reference_answer=references[0]['answer'] if len(references)==1 else (
            'Các tài liệu tham khảo có nội dung giờ phục vụ khác nhau; chưa có căn cứ chọn lịch hiện hành cho từng cơ sở. '
            'Hãy xác nhận với thư viện trước khi đến. Không tự áp dụng lịch dưới đây cho hôm nay:\n\n'+
            '\n\n'.join(row['source_title']+':\n'+row['answer'] for row in references))
        if 'hom nay' not in q and references:
            return result(reference_answer,'needs_confirmation',[source(row) for row in references])
        if not branches or 'hom nay' not in q:
            return result('Bạn muốn xem giờ phục vụ tại cơ sở nào? Vui lòng hỏi kèm cơ sở và ngày cần tra cứu.', 'clarify', suggestions=[f'Giờ mở cửa hôm nay cơ sở {i}' for i in (1,2,3)])
        branch=next(iter(branches))
        now = datetime.now(ZoneInfo('Asia/Ho_Chi_Minh'))
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
        if references:
            return result('Mình chưa có lịch đã xác nhận cho hôm nay tại cơ sở này. Dưới đây là lịch thường lệ tham khảo, không xác nhận đang mở cửa:\n\n'+reference_answer, 'needs_confirmation',[source(row) for row in references])
    if outside_definition(question) or re.search(r'\b(?:viet|tao|sinh) (?:giup (?:toi|minh) )?(?:code|ma nguon|bai van)\b',q):
        return library_redirect(question)
    rows = published_rows(state.db)
    procedure=is_borrowing_procedure(question)
    if guidance:
        rows=[r for r in rows if normalize(r['question'])==normalize(guidance)]
    elif procedure:
        at_desk = re.search(r'\b(?:tai|o|ra|den) quay\b', q)
        if not at_desk and re.search(r'\b(opac|online|truc tuyen|dat cho)\b',q):
            rows=[r for r in rows if r['category'] in ('renewal','opac') and any(normalize(k) in ('dang ky muon','dat cho','dat muon') for k in r['keywords'])]
        else:
            rows=[r for r in rows if r['category']=='borrowing_guide']
    retrieval_question=guidance or question
    ranked = keyword_search(retrieval_question, rows)
    if not ranked and not library_question(question,history):
        return library_redirect(question)
    if not ranked and not library_subject(question):
        return result('Bạn đang hỏi tiếp về dịch vụ thư viện nào, ở cơ sở và ngày nào? Mình cần thông tin cụ thể để đối chiếu nguồn, chưa thể xác nhận từ câu hỏi ngắn này.', 'clarify',suggestions=SUGGESTIONS)
    asks_fee = bool(re.search(r'\b(phi|'+PENALTY_WORD+r'|qua han)\b',q))
    asks_loan_term = bool(re.search(r'\b(thoi han|han tra|thoi gian muon|muon bao lau|bao nhieu ngay)\b',q))
    if procedure:
        asks_loan_term = asks_loan_term or asks_return_date or bool(re.search(r'\bbao lau\b', q))
    asks_renewal = bool(re.search(r'\b(?:(?:co|duoc) gia han|gia han (?:duoc |toi da )?(?:may lan|bao nhieu|bao lau))\b',q))
    policy_query = asks_fee or asks_loan_term or bool(re.search(r'\b(mo cua|dong cua)\b',q))
    sensitive = bool(guidance) or procedure or policy_query or bool(re.search(r'\b(gia han|mat khau)\b',q))
    vectors=state.vectors if os.getenv('ENABLE_VECTORS','true').lower()=='true' and not state.settings.testing and not sensitive else None
    if procedure and len(rows)==1:
        # A reviewed service category is stronger than shared words about books/accounts.
        retrieval={'ranked':[(rows[0],1)],'method':'keyword'}
    else:
        retrieval=retrieve_knowledge(retrieval_question,rows,None if procedure else vectors)
    ranked=retrieval['ranked']
    semantic=retrieval['method'] in ('hybrid','semantic')
    if not ranked:
        return result('Mình chưa tìm được thông tin đủ căn cứ cho câu hỏi này. Bạn có thể hỏi rõ tên dịch vụ, cơ sở hoặc cách tra cứu cần hỗ trợ.', 'not_found',suggestions=SUGGESTIONS)
    top, score = ranked[0]
    if policy_query and not procedure and not (top['status']=='verified' and top.get('verified_by') and top.get('valid_from') and top.get('valid_until')):
        return result('Mình chưa có thông tin hiện hành đã được thư viện xác nhận cho nội dung này. Vui lòng xác nhận với thư viện trước khi áp dụng lịch, phí hoặc thời hạn; mình không tự suy ra từ tài liệu cũ.',
                      'needs_confirmation',[source(top)])
    if len(ranked)>1 and score<1 and ranked[1][1]>=score-0.08 and ranked[1][0]['category']!=top['category']:
        return result('Có nhiều nội dung có thể liên quan. Bạn chọn câu hỏi gần nhất hoặc hỏi riêng từng ý nhé.', 'clarify', suggestions=[r['question'] for r,_ in ranked[:3]])
    unconfirmed = top['status']=='needs_confirmation'
    if top['category'] in ('hours','fees','policy') and top['status']!='verified':
        unconfirmed = True
    if semantic and sensitive and top['category'] not in ('hours','fees','policy','renewal','support'):
        return result('Chưa tìm được nguồn nghiệp vụ phù hợp để xác nhận. Hãy liên hệ thư viện hoặc hỏi cụ thể hơn.', 'needs_confirmation',suggestions=SUGGESTIONS)
    answer, selected, mode = top['answer'], [top], 'faq'
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
    return result(answer, 'needs_confirmation' if unconfirmed else 'answered',[source(r) for r in selected],mode=mode)
