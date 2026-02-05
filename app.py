import os
from pathlib import Path

print("RUNNING FROM:", os.getcwd())

# Load .env locally (Render ignores this safely)
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(dotenv_path=env_path)
except Exception:
    pass


from flask import Flask, request, send_file, redirect
import sqlite3
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
import stripe



#----------APP----------
app=Flask(__name__)

#----------ENV/STRIPE----------
STRIPE_SECRET_KEY=os.environ.get("STRIPE_SECRET_KEY","").strip()
STRIPE_PRICE_ID=os.environ.get("STRIPE_PRICE_ID","").strip()
STRIPE_WEBHOOK_SECRET=os.environ.get("STRIPE_WEBHOOK_SECRET","").strip()
BASE_URL=os.environ.get("BASE_URL","").strip()

ifnotSTRIPE_SECRET_KEY:
raiseRuntimeError("STRIPE_SECRET_KEYmissing")

ifnotSTRIPE_PRICE_ID:
raiseRuntimeError("STRIPE_PRICE_IDmissing")

ifnotSTRIPE_WEBHOOK_SECRET:
raiseRuntimeError("STRIPE_WEBHOOK_SECRETmissing")

ifnotBASE_URL:
raiseRuntimeError("BASE_URLmissing")

stripe.api_key=STRIPE_SECRET_KEY


#----------APPCONFIG----------
DATABASE="invoices.db"
FREE_INVOICE_LIMIT=3




#=================STRIPECONFIG=================


#=================================================


#----------DATABASE----------


definit_db():
conn=sqlite3.connect(DATABASE)
c=conn.cursor()

c.execute("""
CREATETABLEIFNOTEXISTSinvoices(
idINTEGERPRIMARYKEYAUTOINCREMENT,
clientTEXT,
itemTEXT,
amountREAL
)
""")

c.execute("""
CREATETABLEIFNOTEXISTSsettings(
keyTEXTPRIMARYKEY,
valueTEXT
)
""")

c.execute("""
INSERTORIGNOREINTOsettings(key,value)
VALUES('is_paid','0')
""")

conn.commit()
conn.close()
init_db()




#----------HELPERS----------
defis_paid():
conn=sqlite3.connect(DATABASE)
c=conn.cursor()

c.execute("SELECTvalueFROMsettingsWHEREkey='is_paid'")
row=c.fetchone()

conn.close()

returnrowisnotNoneandrow[0]=="1"


fromdatetimeimportdatetime

defformat_invoice_number(invoice_id):
year=datetime.now().year
returnf"{year}-INV-{str(invoice_id).zfill(4)}"

defget_user_status():
return"ProUser✅"ifis_paid()else"FreeUser(3invoicesmax)"

defget_user_status():
ifis_paid():
return"Pro(Unlimited)"
returnf"Free({FREE_INVOICE_LIMIT}invoicesmax)"

definvoice_count():
conn=sqlite3.connect(DATABASE)
c=conn.cursor()
c.execute("SELECTCOUNT(*)FROMinvoices")
count=c.fetchone()[0]
conn.close()
returncount




#----------STYLES----------

PAGE_STYLE="""
<style>
body{
font-family:Arial,sans-serif;
background:#f4f6f8;
padding:40px;
}
.container{
max-width:500px;
background:white;
padding:30px;
border-radius:8px;
}
input,button{
width:100%;
padding:10px;
margin-top:6px;
}
button{
background:#007bff;
color:white;
border:none;
margin-top:20px;
cursor:pointer;
}
a{
display:block;
margin-top:15px;
}
.invoice-card{
border:1pxsolid#e1e5ea;
padding:15px;
border-radius:6px;
margin-bottom:15px;
background:#fafafa;
}

.invoice-number{
font-weight:bold;
font-size:16px;
margin-bottom:6px;
}

.invoice-meta{
color:#555;
margin-bottom:8px;
}

.invoice-actionsa{
font-size:14px;
text-decoration:none;
color:#007bff;
}

</style>
"""

FOOTER="""
<footerstyle="margin-top:40px;text-align:center;font-size:12px;color:#777;">
©2026MikeCalderon—InvoiceGenerator
</footer>
"""


#----------ROUTES----------

@app.route("/")
defhome():
count=invoice_count()
paid=is_paid()

limit_reached=(notpaidandcount>=FREE_INVOICE_LIMIT)

status="Pro(Unlimited)"ifpaidelsef"Free({FREE_INVOICE_LIMIT-count}invoicesleft)"

button_html="""
<buttontype="submit">SaveInvoice</button>
"""

iflimit_reached:
button_html="""
<buttontype="submit"disabledstyle="background:#ccc;cursor:not-allowed;">
FreeLimitReached
</button>
<pstyle="color:#c00;margin-top:10px;">
You’vereachedthefreelimit.
<ahref="/upgrade">Upgradetocontinue</a>
</p>
"""

returnPAGE_STYLE+f"""
<divclass="container">
<h2>CreateInvoice</h2>

<pstyle="color:#666;font-size:14px;">
Status:{status}
</p>

<formmethod="post"action="/create">
ClientName
<inputtype="text"name="client"required>

Item
<inputtype="text"name="item"required>

Amount($)
<inputtype="number"name="amount"required>

{button_html}
</form>

<ahref="/invoices">ViewAllInvoices</a>
</div>
"""+FOOTER




@app.route("/create",methods=["POST"])
defcreate():
conn=sqlite3.connect(DATABASE)
c=conn.cursor()
c.execute("SELECTCOUNT(*)FROMinvoices")
count=c.fetchone()[0]

ifnotis_paid()andcount>=FREE_INVOICE_LIMIT:

conn.close()
returnPAGE_STYLE+"""
<divclass="container">
<h2>FreeLimitReached</h2>
<p>You’vecreatedthemaximumof3freeinvoices.</p>

<ahref="/upgrade">Upgradetocreateunlimitedinvoices</a>
<ahref="/invoices">Viewyourinvoices</a>
</div>
"""+FOOTER

client=request.form["client"]
item=request.form["item"]
amount=request.form["amount"]

c.execute(
"INSERTINTOinvoices(client,item,amount)VALUES(?,?,?)",
(client,item,amount)
)
invoice_id=c.lastrowid
conn.commit()
conn.close()

returnPAGE_STYLE+f"""
<divclass="container">
<h2>InvoiceSaved</h2>
<p><strong>Invoice{format_invoice_number(invoice_id)}</strong></p>
<p><strong>{client}</strong></p>
<p>{item}</p>
<p>${amount}</p>

<ahref="/pdf/{invoice_id}">DownloadPDF</a>
<ahref="/invoices">Viewallinvoices</a>
<ahref="/">Createanother</a>
</div>
"""+FOOTER


@app.route("/invoices")
definvoices():
conn=sqlite3.connect(DATABASE)
c=conn.cursor()
c.execute("SELECTid,client,item,amountFROMinvoicesORDERBYidDESC")
rows=c.fetchall()
conn.close()

html=PAGE_STYLE+"""
<divclass="container">
<h2>AllInvoices</h2>
"""

ifnotrows:
html+="""
<pstyle="color:#666;text-align:center;">
Noinvoicesyet.Createyourfirstone👇
</p>
<ahref="/">CreateInvoice</a>
</div>
"""
returnhtml+FOOTER

forrinrows:
html+=f"""
<divclass="invoice-card">
<divclass="invoice-number">
{format_invoice_number(r[0])}
</div>

<divclass="invoice-meta">
<strong>{r[1]}</strong><br>
{r[2]}—${r[3]}
</div>

<divclass="invoice-actions">
<ahref="/pdf/{r[0]}">DownloadPDF</a>
</div>
</div>
"""

html+="<ahref='/'>Back</a></div>"
returnhtml+FOOTER


@app.route("/pdf/<int:invoice_id>")
defpdf(invoice_id):
conn=sqlite3.connect(DATABASE)
c=conn.cursor()

#Countinvoices
c.execute("SELECTCOUNT(*)FROMinvoices")
count=c.fetchone()[0]

#BlockPDFifoverfreelimit
ifcount>FREE_INVOICE_LIMITandnotis_paid():
conn.close()
returnPAGE_STYLE+"""
<divclass="container">
<h2>UpgradeRequired🔒</h2>
<p>
You’vereachedthefreeinvoicelimit.<br>
UpgradetounlockunlimitedinvoicesandPDFdownloads.
</p>

<ahref="/upgrade">UpgradeNow</a>
<ahref="/invoices">Backtoinvoices</a>
</div>
"""+FOOTER

#OtherwisegeneratePDF
c.execute(
"SELECTclient,item,amountFROMinvoicesWHEREid=?",
(invoice_id,)
)
invoice=c.fetchone()
conn.close()

ifnotinvoice:
return"Invoicenotfound",404

filename=f"invoice_{invoice_id}.pdf"
file_path=os.path.join(os.getcwd(),filename)

pdf=canvas.Canvas(file_path,pagesize=LETTER)
pdf.setFont("Helvetica",12)

pdf.drawString(100,750,f"INVOICE{format_invoice_number(invoice_id)}")
pdf.drawString(100,700,f"Client:{invoice[0]}")
pdf.drawString(100,680,f"Item:{invoice[1]}")
pdf.drawString(100,660,f"Amount:${invoice[2]}")

pdf.setFont("Helvetica",8)
pdf.drawCentredString(300,30,"©2026MikeCalderon—InvoiceGenerator")

pdf.showPage()
pdf.save()

returnsend_file(file_path,as_attachment=True)



@app.route("/success")
defsuccess():
conn=sqlite3.connect(DATABASE)
c=conn.cursor()
c.execute("""
UPDATEsettings
SETvalue='1'
WHEREkey='is_paid'
""")
conn.commit()
conn.close()

@app.route("/success")
defsuccess():
conn=sqlite3.connect(DATABASE)
c=conn.cursor()
c.execute("""
UPDATEsettings
SETvalue='1'
WHEREkey='is_paid'
""")
conn.commit()
conn.close()

returnPAGE_STYLE+"""
<divclass="container">
<h2>PaymentSuccessful🎉</h2>
<p>YounowhaveunlimitedinvoicesandPDFdownloads.</p>

<ahref="/">Createinvoice</a>
<ahref="/invoices">Viewinvoices</a>
</div>
"""+FOOTER

#----------RUN----------
fromflaskimportabort
importjson

@app.route("/webhook",methods=["POST"])
defstripe_webhook():
payload=request.data
sig_header=request.headers.get("Stripe-Signature")

event=stripe.Webhook.construct_event(
payload,
sig_header,
STRIPE_WEBHOOK_SECRET
)

ifevent["type"]=="checkout.session.completed":
conn=sqlite3.connect(DATABASE)
c=conn.cursor()

c.execute("""
INSERTORREPLACEINTOsettings(key,value)
VALUES('is_paid','1')
""")

conn.commit()
conn.close()

return"",200


#----------RUN----------

if__name__=="__main__":
app.run(host="0.0.0.0",port=10000)



