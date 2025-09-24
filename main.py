import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog,messagebox
import json
import os
from datetime import datetime

# PDF & Signing Imports
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from pyhanko.sign import signers
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from jose import jws

# --- Core Logic ---

def sign_json_data(data):
    """Signs the JSON data using JWS."""
    try:
        with open('key.pem','rb') as f:
            private_key=f.read()
    except FileNotFoundError:
        raise FileNotFoundError("Signing key 'key.pem' not found.")

    payload=data.copy()
    if 'audit' in payload and 'digital_signature' in payload['audit']:
        payload['audit']['digital_signature']=None
    
    payload_json=json.dumps(payload,separators=(',',':'))
    signature=jws.sign(payload_json.encode('utf-8'),private_key,algorithm='RS256')
    
    signed_data=data.copy()
    signed_data['audit']['digital_signature']=signature
    return signed_data

def create_certificate_pdf(path,data):
    """Creates the visual PDF certificate."""
    doc=SimpleDocTemplate(path,pagesize=A4,rightMargin=50,leftMargin=50,topMargin=50,bottomMargin=50)
    story=[]
    styles=getSampleStyleSheet()
    
    story.append(Paragraph("<para align=center><b><font size=18 color=navy>SSD WIPE CERTIFICATE OF DATA DESTRUCTION</font></b></para>",styles['Normal']))
    story.append(Spacer(1,20))
    
    story.append(Paragraph("<b>Device Information:</b>",styles['Heading3']))
    device=data.get('device',{})
    capacity_gb=device.get('capacity_bytes',0)/(1024**3) if device.get('capacity_bytes') else 0
    device_data=[
        ['Device Type:',device.get('device_type','N/A')],
        ['Model:',device.get('model','N/A')],
        ['Serial:',device.get('serial_number','N/A')],
        ['Capacity:',f"{capacity_gb:.1f} GB"],
    ]
    device_table=Table(device_data,colWidths=[1.5*inch,3.5*inch])
    device_table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(0,-1),colors.lightblue),
        ('GRID',(0,0),(-1,-1),1,colors.black),
    ]))
    story.append(device_table)
    story.append(Spacer(1,15))
    
    story.append(Paragraph("<b>Wipe Process:</b>",styles['Heading3']))
    wipe=data.get('wipe_process',{})
    duration_mins=wipe.get('duration_seconds',0)/60
    wipe_data=[
        ['Method:',wipe.get('wipe_method','N/A')],
        ['Started:',wipe.get('start_time','N/A')],
        ['Finished:',wipe.get('end_time','N/A')],
        ['Duration:',f"{duration_mins:.1f} minutes"],
        ['Status:',data.get('verification',{}).get('verification_status','N/A').upper()],
    ]
    wipe_table=Table(wipe_data,colWidths=[1.5*inch,3.5*inch])
    wipe_table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(0,-1),colors.lightgreen),
        ('GRID',(0,0),(-1,-1),1,colors.black),
    ]))
    story.append(wipe_table)
    story.append(Spacer(1,30))
    
    doc.build(story)

def apply_pdf_signature(unsigned_path,signed_path):
    """Applies a cryptographic signature to an existing PDF."""
    signer=signers.SimpleSigner.load(key_file='key.pem',cert_file='cert.pem')
    with open(unsigned_path,'rb') as doc_in,open(signed_path,'wb') as doc_out:
        writer=IncrementalPdfFileWriter(doc_in)
        signers.sign_pdf(writer,signers.PdfSignatureMetadata(field_name='Signature1'),signer=signer,output=doc_out)

# --- UI Functions ---

def browse_json_file():
    """Opens file dialog and loads JSON data into the UI."""
    global json_data
    path=filedialog.askopenfilename(title="Select JSON file",filetypes=[("JSON files","*.json")])
    if not path:
        return
        
    file_entry.delete(0,END)
    file_entry.insert(0,path)
    try:
        with open(path,'r',encoding='utf-8') as f:
            json_data=json.load(f)
        preview_text.delete(1.0,END)
        preview_text.insert(1.0,json.dumps(json_data,indent=2))
        status_label.config(text=f"Loaded: {os.path.basename(path)}")
        generate_btn.config(state=NORMAL)
    except Exception as e:
        messagebox.showerror("Error",f"Couldn't load JSON: {str(e)}")
        status_label.config(text="Error loading file")
        generate_btn.config(state=DISABLED)

def clear_everything():
    """Resets the UI to its initial state."""
    global json_data
    json_data=None
    file_entry.delete(0,END)
    preview_text.delete(1.0,END)
    status_label.config(text="Ready")
    generate_btn.config(state=DISABLED)

def generate_files():
    """The main function to generate all signed files."""
    if not json_data:
        return messagebox.showerror("Error","No JSON data loaded!")
    
    save_base=filedialog.asksaveasfilename(title="Choose a base name for output...",defaultextension=".pdf",filetypes=[("PDF files","*.pdf")])
    if not save_base:
        return
        
    signed_json_path=save_base.replace(".pdf","-signed.json")
    signed_pdf_path=save_base
    unsigned_path=save_base.replace(".pdf","-unsigned-temp.pdf")

    try:
        status_label.config(text="Signing JSON...")
        root.update_idletasks()
        signed_data=sign_json_data(json_data)
        with open(signed_json_path,'w') as f:
            json.dump(signed_data,f,indent=2)
        
        status_label.config(text="Creating PDF...")
        root.update_idletasks()
        create_certificate_pdf(unsigned_path,signed_data)
        
        status_label.config(text="Signing PDF...")
        root.update_idletasks()
        apply_pdf_signature(unsigned_path,signed_pdf_path)
        
        os.remove(unsigned_path)
        status_label.config(text="Success! Files created.")
        messagebox.showinfo("Success",f"Files created:\n1. {os.path.basename(signed_json_path)}\n2. {os.path.basename(signed_pdf_path)}")
        
    except Exception as e:
        messagebox.showerror("Error",f"An error occurred: {str(e)}")
        status_label.config(text="Error")

# --- GUI Setup ---

json_data=None

root=ttk.Window(themename="superhero") 
root.title("SSD Wipe Certificate Tool")
root.geometry("700x600")

main_frame=ttk.Frame(root,padding=20)
main_frame.pack(fill=BOTH,expand=YES)

load_frame=ttk.LabelFrame(main_frame,text="Step 1: Load Data",padding=15)
load_frame.pack(fill=X,pady=(0,15))
file_entry=ttk.Entry(load_frame,font=("-size",11))
file_entry.pack(side=LEFT,fill=X,expand=YES,padx=(0,15))
browse_btn=ttk.Button(load_frame,text="Load Wipe Data File (.json)",command=browse_json_file,bootstyle="primary")
browse_btn.pack(side=LEFT)

preview_frame=ttk.LabelFrame(main_frame,text="JSON Preview",padding=10)
preview_frame.pack(fill=BOTH,expand=YES,pady=(0,15))
preview_text=tk.Text(preview_frame,wrap=WORD,height=10,font=("Consolas",10),relief="flat")
preview_text.pack(side=LEFT,fill=BOTH,expand=YES)
scrollbar=ttk.Scrollbar(preview_frame,orient=VERTICAL,command=preview_text.yview,bootstyle="round")
scrollbar.pack(side=RIGHT,fill=Y)
preview_text.config(yscrollcommand=scrollbar.set)

action_frame=ttk.LabelFrame(main_frame,text="Step 2: Generate Certificate",padding=15)
action_frame.pack(fill=X,pady=(0,15))
generate_btn=ttk.Button(action_frame,text="Generate Signed Certificate Files",command=generate_files,bootstyle="success",state=DISABLED)
generate_btn.pack(fill=X)

clear_btn=ttk.Button(main_frame,text="Clear Form",command=clear_everything,bootstyle="secondary-outline")
clear_btn.pack(fill=X,pady=(0,20))

status_label=ttk.Label(main_frame,text="Ready",font=("-size",10),bootstyle="secondary")
status_label.pack(side=BOTTOM,fill=X)

if __name__=="__main__":
    root.mainloop()