import pickle, time, sys
from pathlib import Path
import numpy as np
CACHE = Path('_cache')
c = pickle.loads((CACHE/'corpus.pkl').read_bytes())
docs = c['docs']
from sentence_transformers import SentenceTransformer
m = SentenceTransformer('BAAI/bge-m3', device='cuda')
m.half()
m.max_seq_length = 512          # 與 bge-small 同一輸入預算，確保公平比較
print(f'bge-m3 載入完成 dim={m.get_sentence_embedding_dimension()} max_len={m.max_seq_length}', flush=True)
out = CACHE/'emb_m3.npy'
B = 1000
parts = []
t0 = time.time()
for i in range(0, len(docs), B):
    v = m.encode(docs[i:i+B], batch_size=8, normalize_embeddings=True,
                 show_progress_bar=False)
    parts.append(np.asarray(v, dtype=np.float32))
    el = time.time()-t0
    done = min(i+B, len(docs))
    print(f'  {done:,}/{len(docs):,}  已耗時 {el/60:.1f} 分，預估總計 {el/done*len(docs)/60:.0f} 分', flush=True)
np.save(out, np.vstack(parts))
print('完成', out, flush=True)
