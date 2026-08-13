"""Global Streamlit styles."""

CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+KR:wght@400;500;600;700&display=swap');
:root{--blue:#2864dc;--red:#e5484d;--ink:#161b26;--muted:#717784;--line:#e8ebf0}
.stApp{background:#f7f8fb;color:var(--ink);font-family:Inter,'Noto Sans KR',sans-serif}
.block-container{max-width:1240px;padding:4.25rem 2rem 4rem!important}
[data-testid=stSidebar]{background:#fff;border-right:1px solid var(--line)}
[data-testid=stSidebar] .block-container{padding:1.35rem 1rem}
.brand{display:flex;align-items:center;gap:.6rem;font-weight:700;font-size:1.15rem;margin:.2rem 0 1.5rem}
.mark{display:grid;place-items:center;width:32px;height:32px;border-radius:10px;color:#fff;background:var(--blue)}
.side-title{font-size:.73rem;font-weight:700;color:#959baa;letter-spacing:.08em;margin:1.25rem 0 .45rem}
.page-head{display:flex;align-items:end;justify-content:space-between;margin-bottom:1.2rem}
.page-head h1{font-size:1.75rem;letter-spacing:-.04em;margin:0}
.page-head p,.caption{color:var(--muted);font-size:.82rem;margin:.35rem 0 0}
.card{background:#fff;border:1px solid var(--line);border-radius:18px;padding:1.35rem;box-shadow:0 7px 24px rgba(20,30,50,.035)}
.rank-row{display:grid;grid-template-columns:38px 1fr 100px 100px 115px;align-items:center;padding:.82rem .4rem;border-bottom:1px solid #f0f2f5;font-size:.82rem}
.rank-row:last-child{border:0}.rank{color:#9198a5;font-weight:600}.sym{font-weight:700}
.sub{font-size:.68rem;color:var(--muted);margin-top:.15rem}.num{text-align:right;font-variant-numeric:tabular-nums}
.rate{color:var(--blue);font-weight:600}.negative{color:var(--red)!important}
.stock-head{display:flex;align-items:center;justify-content:space-between}.stock-head h2{margin:0;font-size:1.55rem}
.price{font-size:1.5rem;font-weight:700;text-align:right}.empty{padding:3rem;text-align:center;color:var(--muted)}
.stButton button{width:100%;border-radius:10px}.stTextInput input{border-radius:10px}
.login-shell{min-height:66vh;display:flex;flex-direction:column;justify-content:center}
.login-kicker{display:inline-flex;align-items:center;gap:.5rem;color:var(--blue);background:#edf3ff;border-radius:99px;padding:.45rem .75rem;font-size:.72rem;font-weight:700;letter-spacing:.04em}
.login-title{font-size:3.35rem;line-height:1.13;letter-spacing:-.065em;margin:1.15rem 0 1rem;max-width:650px}
.login-copy{font-size:1rem;line-height:1.8;color:var(--muted);max-width:560px}
.feature-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:.7rem;margin-top:1.5rem;max-width:620px}
.feature{background:#fff;border:1px solid var(--line);border-radius:15px;padding:1rem}
.feature-icon{display:grid;place-items:center;width:30px;height:30px;border-radius:9px;background:#f0f4ff;color:var(--blue);font-size:.8rem;font-weight:700}
.feature strong{display:block;font-size:.78rem;margin:.7rem 0 .2rem}.feature small{font-size:.67rem;color:var(--muted);line-height:1.45}
.login-card{background:#fff;border:1px solid var(--line);border-radius:24px;padding:1.8rem;box-shadow:0 20px 55px rgba(25,42,75,.09);margin-top:2rem}
.login-card-head{display:flex;align-items:center;gap:.8rem;margin-bottom:1.35rem}
.login-logo{display:grid;place-items:center;width:42px;height:42px;border-radius:13px;background:#edf3ff;color:var(--blue);font-weight:800}
.login-card h3{margin:0;font-size:1.08rem}.login-card p{margin:.2rem 0 0;color:var(--muted);font-size:.72rem}
.secure-note{display:flex;gap:.55rem;align-items:flex-start;background:#f7f9fc;border-radius:12px;padding:.8rem;margin-top:.9rem;color:#687083;font-size:.68rem;line-height:1.5}
.steps{display:flex;justify-content:center;gap:.65rem;margin-top:1.3rem;color:#9aa0ab;font-size:.66rem}.steps b{color:var(--blue)}
.login-help{text-align:center;color:var(--muted);font-size:.69rem;margin-top:1rem}.login-help a{color:var(--blue);text-decoration:none}
.login-card [data-testid=stFormSubmitButton] button{height:47px;background:var(--blue);color:#fff;border:0;font-weight:700}
.login-card [data-testid=stTextInput] label{font-size:.75rem;font-weight:600}
.login-card [data-testid=stTextInput] input{height:46px;background:#fbfcfe;border-color:#e2e6ed}
.brand-story{display:flex;align-items:center;gap:.65rem;margin-top:1.15rem;color:#4f596b;font-size:.76rem}
.brand-story b{color:var(--ink);font-size:.83rem}.brand-story i{width:1px;height:14px;background:#cfd4dd}
@media(max-width:800px){
  .block-container{padding:3.5rem 1rem 3rem!important}
  .rank-row{grid-template-columns:32px 1fr 80px 80px}.rank-row>:nth-child(4){display:none}
  .login-shell{min-height:auto}.login-title{font-size:2.4rem}.feature-grid{grid-template-columns:1fr}.login-card{margin-top:1rem}
}
</style>"""
