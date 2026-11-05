import { useState } from 'react'
import { ExternalLink, Icon, Modal } from './UI.jsx'
import page3 from '../assets/opac-guide/opac-page-3.webp'
import page4 from '../assets/opac-guide/opac-page-4.webp'
import page6 from '../assets/opac-guide/opac-page-6.webp'

const pdf = 'https://opacthuvien.ut.edu.vn/opac/Upload/HDSD_TRACUU_OPAC.v1.1.pdf'
const images = {
  [`${pdf}#page=3`]: { src: page3, page: 3, title: 'Nhập từ khóa và xem kết quả' },
  [`${pdf}#page=4`]: { src: page4, page: 4, title: 'Chọn loại tài liệu' },
  [`${pdf}#page=6`]: { src: page6, page: 6, title: 'Tìm theo nhan đề hoặc tác giả' },
}

export default function GuideImage({ sourceUrl }) {
  const [enlarged, setEnlarged] = useState(false)
  const [failed, setFailed] = useState(false)
  const image = Object.hasOwn(images, sourceUrl) ? images[sourceUrl] : null
  if (!image) return null
  if (failed) return <p className="guide-note">Không tải được ảnh minh họa. Bạn vẫn có thể đọc hướng dẫn và mở nguồn PDF bên dưới.</p>
  return <figure className="guide-image">
    <button type="button" className="guide-preview" aria-label={`Phóng to hình: ${image.title}`} onClick={() => setEnlarged(true)}>
      <img src={image.src} alt={`OPAC: ${image.title} (trang ${image.page})`} width="1237" height="1600" loading="lazy" decoding="async" onError={() => setFailed(true)} />
      <span><Icon name="search" size={16} /> Phóng to hình hướng dẫn</span>
    </button>
    <figcaption><strong>{image.title} · Trang {image.page}</strong>
      <p className="guide-note">Giao diện và số liệu trong ảnh là minh họa từ tài liệu hướng dẫn; có thể khác hiện tại.</p>
      <ExternalLink href={sourceUrl}>Xem trang {image.page} trong PDF gốc</ExternalLink>
    </figcaption>
    {enlarged && <Modal title={`Hình hướng dẫn - Trang ${image.page}`} onClose={() => setEnlarged(false)}>
      <img className="guide-full-image" src={image.src} alt={`OPAC: ${image.title} (trang ${image.page})`} width="1237" height="1600" decoding="async" onError={() => setFailed(true)} />
      <div className="inline-actions"><a href={image.src} target="_blank" rel="noopener noreferrer">Mở ảnh kích thước gốc</a>
        <ExternalLink href={sourceUrl}>Xem trang {image.page} trong PDF gốc</ExternalLink></div>
    </Modal>}
  </figure>
}
