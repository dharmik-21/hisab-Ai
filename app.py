import streamlit as st
import pandas as pd
from datetime import date
import plotly.express as px
from database import engine, SessionLocal, Base
from models import Invoice, Item
from ai import extract_text, extract_items, calculate_totals

# PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# ================= UI =================
st.set_page_config(page_title="HisabAI", layout="wide")

st.markdown("""
<style>
.stApp {background: #0f172a; color: white;}
section[data-testid="stSidebar"] {background: #020617;}
[data-testid="stMetric"] {
    background: #1e293b;
    padding: 15px;
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)

# ================= DB =================
Base.metadata.create_all(bind=engine)
db = SessionLocal()

st.title("💼 HisabAI")

menu = st.sidebar.selectbox("Menu", [
    "Dashboard",
    "Upload Invoice",
    "View Invoices",
    "Chat AI"
])

# ================= PDF =================
def generate_invoice_pdf(items, totals):

    doc = SimpleDocTemplate("invoice.pdf")
    styles = getSampleStyleSheet()

    elements = []
    elements.append(Paragraph("INVOICE", styles["Title"]))
    elements.append(Spacer(1, 10))

    data = [["Item", "Price"]]

    for item in items:
        data.append([item["name"], str(item["price"])])

    data.append(["", ""])
    data.append(["Subtotal", totals["subtotal"]])
    data.append(["CGST", totals["cgst"]])
    data.append(["SGST", totals["sgst"]])
    data.append(["TOTAL", totals["total"]])

    table = Table(data)

    table.setStyle([
        ("GRID", (0,0), (-1,-1), 1, colors.black),
        ("BACKGROUND", (0,0), (-1,0), colors.grey),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
    ])

    elements.append(table)
    doc.build(elements)

    return "invoice.pdf"

# ================= UPLOAD =================
if menu == "Upload Invoice":

    file = st.file_uploader("Upload Invoice", type=["png","jpg","jpeg"])

    if file:
        text = extract_text(file)
        items = extract_items(text)
        totals = calculate_totals(items)

        st.subheader("🧾 Invoice")

        # 👉 Build table
        data = [["Item", "Price"]]

        for item in items:
            data.append([item["name"], f"₹{item['price']}"])

        data.append(["", ""])
        data.append(["Subtotal", f"₹{totals['subtotal']}"])
        data.append(["CGST", f"₹{totals['cgst']}"])
        data.append(["SGST", f"₹{totals['sgst']}"])
        data.append(["TOTAL", f"₹{totals['total']}"])

        df_invoice = pd.DataFrame(data[1:], columns=data[0])

        st.table(df_invoice)

        # SAVE
        if st.button("Save"):
            invoice = Invoice(**totals)
            db.add(invoice)
            db.commit()

            for item in items:
                db.add(Item(
                    name=item["name"],
                    price=item["price"],
                    invoice_id=invoice.id
                ))

            db.commit()
            st.success("Saved")

        # PDF
        if st.button("Download PDF"):
            path = generate_invoice_pdf(items, totals)
            with open(path, "rb") as f:
                st.download_button("Download", f, "invoice.pdf")

# ================= VIEW =================
elif menu == "View Invoices":

    st.subheader("📄 View Invoices")

    # 🔍 Date filter
    search_date = st.date_input("Select Date to Search")

    invoices = db.query(Invoice).all()

    filtered_invoices = []

    for inv in invoices:
        if search_date:
            if inv.date == search_date:
                filtered_invoices.append(inv)
        else:
            filtered_invoices.append(inv)

    if not filtered_invoices:
        st.warning("No invoices found for selected date")

    for inv in filtered_invoices:

        st.markdown("---")
        st.subheader(f"Invoice #{inv.id} | 📅 {inv.date}")

        items = db.query(Item).filter(Item.invoice_id == inv.id).all()

        # 👉 Build table
        data = [["Item", "Price"]]

        for i in items:
            data.append([i.name, f"₹{i.price}"])

        data.append(["", ""])
        data.append(["Subtotal", f"₹{inv.subtotal}"])
        data.append(["CGST", f"₹{inv.cgst}"])
        data.append(["SGST", f"₹{inv.sgst}"])
        data.append(["TOTAL", f"₹{inv.total}"])

        df_invoice = pd.DataFrame(data[1:], columns=data[0])

        st.table(df_invoice)

        # ================= PDF DOWNLOAD =================
        if st.button(f"Download PDF Invoice #{inv.id}"):

            pdf_items = [{"name": i.name, "price": i.price} for i in items]

            totals = {
                "subtotal": inv.subtotal,
                "cgst": inv.cgst,
                "sgst": inv.sgst,
                "total": inv.total
            }

            pdf_path = generate_invoice_pdf(pdf_items, totals)

            with open(pdf_path, "rb") as f:
                st.download_button(
                    label="Download Invoice",
                    data=f,
                    file_name=f"invoice_{inv.id}.pdf",
                    mime="application/pdf"
                )
# ================= DASHBOARD =================
elif menu == "Dashboard":

    st.title("📊 Dashboard")

    items = db.query(Item).all()

    df = pd.DataFrame([{
        "name": i.name,
        "price": i.price,
        "date": i.invoice.date   # ✅ correct
    } for i in items])

    if not df.empty:

        df["date"] = pd.to_datetime(df["date"])

        # ================= TODAY FILTER =================
        today = pd.Timestamp.today().date()
        today_df = df[df["date"].dt.date == today]

        # ================= MONTH FILTER =================
        current_month = pd.Timestamp.today().month
        month_df = df[df["date"].dt.month == current_month]

        # ================= FINANCIAL =================
        total_sales = df[df["price"] > 0]["price"].sum()
        total_expense = abs(df[df["price"] < 0]["price"].sum())
        profit = total_sales - total_expense

        col1, col2, col3 = st.columns(3)
        col1.metric("💰 Total Sales", f"₹{total_sales}")
        col2.metric("📉 Expense", f"₹{total_expense}")
        col3.metric("📊 Profit", f"₹{profit}")

        # ================= DAILY PRODUCT GRAPH =================
        st.subheader(f"📅 Today's Sales ({today})")

        daily_sales = today_df.groupby("name")["price"].sum().reset_index()

        if not daily_sales.empty:
            fig = px.bar(
                daily_sales,
                x="name",
                y="price",
                color="name",
                text="price"
            )
            fig.update_layout(template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

        # ================= MONTHLY PIE CHART =================
        st.subheader("📅 Monthly Sales Distribution")

        monthly_sales = month_df.groupby("name")["price"].sum().reset_index()

        if not monthly_sales.empty:
            fig = px.pie(
                monthly_sales,
                names="name",
                values="price",
                color_discrete_sequence=px.colors.sequential.RdBu
            )
            fig.update_traces(textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)

        # ================= DATE SETUP =================
        today = pd.Timestamp.today()
        current_year = today.year
        current_month = today.month

        if current_month >= 4:
            fy_start = pd.Timestamp(year=current_year, month=4, day=1)
            fy_end = pd.Timestamp(year=current_year + 1, month=3, day=31)
        else:
            fy_start = pd.Timestamp(year=current_year - 1, month=4, day=1)
            fy_end = pd.Timestamp(year=current_year, month=3, day=31)

        # ================= DAILY SUMMARY =================
        daily_df = df[df["date"].dt.date == today.date()]

        daily_sales_df = daily_df[daily_df["price"] > 0]
        daily_expense_df = daily_df[daily_df["price"] < 0]

        daily_sales = daily_sales_df["price"].sum()
        daily_expense = abs(daily_expense_df["price"].sum())
        daily_profit = daily_sales - daily_expense

        st.subheader("📅 Today's Summary")

        col1, col2, col3 = st.columns(3)

        col1.metric("💰 Today Sales", f"₹{daily_sales}")
        if col1.button("View Sales Details"):
            st.dataframe(daily_sales_df[["name", "price"]])

        col2.metric("📉 Today Expense", f"₹{daily_expense}")
        if col2.button("View Expense Details"):
            st.dataframe(daily_expense_df[["name", "price"]])

        col3.metric("📊 Today Profit", f"₹{daily_profit}")
        if col3.button("View Profit Breakdown"):
            st.write("Sales:")
            st.dataframe(daily_sales_df[["name", "price"]])
            st.write("Expenses:")
            st.dataframe(daily_expense_df[["name", "price"]])

        # ================= MONTHLY SUMMARY =================
        monthly_df = df[df["date"].dt.month == current_month]

        monthly_sales_df = monthly_df[monthly_df["price"] > 0]
        monthly_expense_df = monthly_df[monthly_df["price"] < 0]

        monthly_sales = monthly_sales_df["price"].sum()
        monthly_expense = abs(monthly_expense_df["price"].sum())
        monthly_profit = monthly_sales - monthly_expense

        st.subheader("📅 Monthly Summary")

        col1, col2, col3 = st.columns(3)

        col1.metric("💰 Month Sales", f"₹{monthly_sales}")
        if col1.button("View Monthly Sales"):
            st.dataframe(monthly_sales_df[["name", "price"]])

        col2.metric("📉 Month Expense", f"₹{monthly_expense}")
        if col2.button("View Monthly Expense"):
            st.dataframe(monthly_expense_df[["name", "price"]])

        col3.metric("📊 Month Profit", f"₹{monthly_profit}")
        if col3.button("View Monthly Profit"):
            st.write("Sales:")
            st.dataframe(monthly_sales_df[["name", "price"]])
            st.write("Expenses:")
            st.dataframe(monthly_expense_df[["name", "price"]])

        # ================= FINANCIAL YEAR =================
        fy_df = df[(df["date"] >= fy_start) & (df["date"] <= fy_end)]

        fy_sales_df = fy_df[fy_df["price"] > 0]
        fy_expense_df = fy_df[fy_df["price"] < 0]

        fy_sales = fy_sales_df["price"].sum()
        fy_expense = abs(fy_expense_df["price"].sum())
        fy_profit = fy_sales - fy_expense

        st.subheader("📅 Financial Year Summary")

        col1, col2, col3 = st.columns(3)

        col1.metric("💰 FY Sales", f"₹{fy_sales}")
        if col1.button("View FY Sales"):
            st.dataframe(fy_sales_df[["name", "price"]])

        col2.metric("📉 FY Expense", f"₹{fy_expense}")
        if col2.button("View FY Expense"):
            st.dataframe(fy_expense_df[["name", "price"]])

        col3.metric("📊 FY Profit", f"₹{fy_profit}")
        if col3.button("View FY Profit"):
            st.write("Sales:")
            st.dataframe(fy_sales_df[["name", "price"]])
            st.write("Expenses:")
            st.dataframe(fy_expense_df[["name", "price"]])

        # ================= PREDICTION =================
        # ================= AI INSIGHTS =================
        st.subheader("🧠 AI Insights")

# Monthly trend for insight
        df["month"] = df["date"].dt.to_period("M")
        monthly_trend = df.groupby("month")["price"].sum().reset_index()

        if len(monthly_trend) >= 2:

              last = monthly_trend.iloc[-1]["price"]
              prev = monthly_trend.iloc[-2]["price"]

            
            
              if prev != 0:

                   change = ((last - prev) / prev) * 100

                   if change > 0:
                        st.success(f"📈 Sales increased by {round(change,2)}% compared to last month")
                   else:
                        st.error(f"📉 Sales dropped by {round(abs(change),2)}% compared to last month")

# ================= LINE GRAPH =================
        st.subheader("📈 Sales Trend")

        monthly_trend["month"] = monthly_trend["month"].astype(str)

        fig_line = px.line(
            monthly_trend,
            x="month",
            y="price",
            markers=True
        )

        fig_line.update_layout(template="plotly_dark")

        st.plotly_chart(fig_line, use_container_width=True)

# ================= CHAT =================
elif menu == "Chat AI":

    st.subheader("💬 Ask HisabAI")

    q = st.text_input("Ask... (example: sales on 2026-03-19)")

    items = db.query(Item).all()

    df = pd.DataFrame([{
    "name": i.name,
    "price": i.price,
    "date": i.invoice.date   # ✅ correct
} for i in items])

    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])

    if q and not df.empty:
        q = q.lower()

        import re
        match = re.search(r'\d{4}-\d{2}-\d{2}', q)

        if match:
            user_date = pd.to_datetime(match.group())
            df = df[df["date"].dt.date == user_date.date()]

        product_sales = df.groupby("name")["price"].sum()

        if "top" in q:
            st.write(product_sales.idxmax())

        elif "total" in q:
            st.write(f"₹{df['price'].sum()}")

        elif "profit" in q:
            sales = df[df["price"] > 0]["price"].sum()
            expense = abs(df[df["price"] < 0]["price"].sum())
            st.write(f"₹{sales - expense}")

        else:
            st.write("Try: sales on 2026-03-19, profit, top product")