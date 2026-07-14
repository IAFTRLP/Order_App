import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import urllib.parse
from streamlit_calendar import calendar

# 1. 建立並連線到資料庫
conn = sqlite3.connect('dessert_final.db')
c = conn.cursor()

# 自動建立所有需要的資料表
c.execute('''CREATE TABLE IF NOT EXISTS Ingredients
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              name TEXT, current_stock REAL, safety_stock REAL, unit TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS Products
             (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price REAL)''')

c.execute('''CREATE TABLE IF NOT EXISTS Product_BOM
             (product_id INTEGER, ingredient_id INTEGER, required_quantity REAL,
              PRIMARY KEY (product_id, ingredient_id))''')

c.execute('''CREATE TABLE IF NOT EXISTS Orders
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              customer_name TEXT, delivery_date TEXT, 
              name TEXT, status TEXT)''')

# 1. 甜點品項的擴充欄位 (提前製作天數、配方產出量)
try:
    c.execute("ALTER TABLE Products ADD COLUMN prep_days INTEGER DEFAULT 0")
    conn.commit()
except sqlite3.OperationalError:
    pass 

try:
    c.execute("ALTER TABLE Products ADD COLUMN batch_yield INTEGER DEFAULT 1")
    conn.commit()
except sqlite3.OperationalError:
    pass

# 2. 成本分析的擴充欄位 (物料單價、包材費、雜支)
try:
    c.execute("ALTER TABLE Ingredients ADD COLUMN unit_price REAL DEFAULT 0.0")
    conn.commit()
except sqlite3.OperationalError:
    pass

try:
    c.execute("ALTER TABLE Products ADD COLUMN packaging_cost REAL DEFAULT 0.0")
    conn.commit()
except sqlite3.OperationalError:
    pass

try:
    c.execute("ALTER TABLE Products ADD COLUMN overhead_cost REAL DEFAULT 0.0")
    conn.commit()
except sqlite3.OperationalError:
    pass

try:
    c.execute("ALTER TABLE Products ADD COLUMN overhead_cost REAL DEFAULT 0.0")
    conn.commit()
except sqlite3.OperationalError:
    pass

# 🌟 全新加入：預設的人事成本欄位
try:
    c.execute("ALTER TABLE Products ADD COLUMN labor_cost REAL DEFAULT 0.0")
    conn.commit()
except sqlite3.OperationalError:
    pass

# 🌟 確保每個欄位都有「獨立」的 try...except
try:
    c.execute("ALTER TABLE Products ADD COLUMN hourly_wage REAL DEFAULT 200.0")
    conn.commit()
except sqlite3.OperationalError:
    pass

try:
    c.execute("ALTER TABLE Products ADD COLUMN production_minutes REAL DEFAULT 0.0")
    conn.commit()
except sqlite3.OperationalError:
    pass

try:
    c.execute("ALTER TABLE Products ADD COLUMN production_hours REAL DEFAULT 0.0")
    conn.commit()
except sqlite3.OperationalError:
    pass

# 網頁介面設計
st.set_page_config(page_title="甜點工作室管理系統", page_icon="🍰", layout="wide", initial_sidebar_state="auto")
st.title("🍰 甜點工作室管理後台")

st.sidebar.header("功能選單")
page = st.sidebar.radio("請選擇頁面", ["庫存總覽", "訂單管理", "配方設定", "成本分析"])

# ===== 頁面 1：庫存總覽 (卡片式內建修改版) =====
if page == "庫存總覽":
    st.subheader("📦 目前物料庫存")
    query = """
    SELECT id, name, 
           CASE 
               WHEN name LIKE '%粉%' THEN '粉類'
               WHEN name LIKE '%糖%' THEN '糖類'
               ELSE '其他'
           END AS category,
           current_stock, unit 
    FROM Ingredients
    """
    df_ingredients = pd.read_sql_query(query, conn)
    
    if df_ingredients.empty:
        st.info("目前資料庫中還沒有物料資料喔！請先在下方新增。")
    else:
        tab_all, tab_flour, tab_sugar, tab_other = st.tabs(["🗂️ 全部", "🍞 粉類", "🍬 糖類", "📦 其他"])
        
        def draw_inventory_cards(df_subset, prefix):
            if df_subset.empty:
                st.caption("目前此分類沒有物料。")
                return
            for _, row in df_subset.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 3, 2])
                    c1.write(f"**{row['name']}**")
                    c2.write(f"📦 {row['current_stock']} {row['unit']}")
                    with c3:
                        with st.popover("✏️ 更新庫存", use_container_width=True):
                            st.markdown(f"調整 **{row['name']}** 的庫存")
                            mode = st.radio("調整方式", ["進貨 (+)", "消耗 (-)", "重新盤點 (=)"], key=f"{prefix}_m_{row['id']}", horizontal=True)
                            amt = st.number_input("異動數量", min_value=0.0, step=10.0, key=f"{prefix}_a_{row['id']}")
                            if st.button("確認更新", key=f"{prefix}_btn_{row['id']}", use_container_width=True):
                                if mode == "進貨 (+)": c.execute("UPDATE Ingredients SET current_stock = current_stock + ? WHERE id = ?", (amt, row['id']))
                                elif mode == "消耗 (-)": c.execute("UPDATE Ingredients SET current_stock = current_stock - ? WHERE id = ?", (amt, row['id']))
                                else: c.execute("UPDATE Ingredients SET current_stock = ? WHERE id = ?", (amt, row['id']))
                                conn.commit()
                                st.toast(f"✨ {row['name']} 庫存更新成功！", icon="💾")
                                st.rerun()

        with tab_all: draw_inventory_cards(df_ingredients, "all")
        with tab_flour: draw_inventory_cards(df_ingredients[df_ingredients['category'] == '粉類'], "flour")
        with tab_sugar: draw_inventory_cards(df_ingredients[df_ingredients['category'] == '糖類'], "sugar")
        with tab_other: draw_inventory_cards(df_ingredients[df_ingredients['category'] == '其他'], "other")

    st.write("---")
    # ─── 區塊：新增原物料品項 ───
    st.subheader("➕ 新增原物料品項")
    
    # 初始化一個專門記錄新增狀態的變數
    if "add_success_msg" not in st.session_state:
        st.session_state.add_success_msg = False

    with st.form("add_ingredient_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1: new_name = st.text_input("物料名稱", placeholder="例如：低筋麵粉")
        with col2: new_stock = st.number_input("初始庫存", min_value=0.0, step=100.0)
        with col3: new_unit = st.text_input("單位", placeholder="例如：g")
        
        if st.form_submit_button("新增品項"):
            if new_name:
                c.execute("INSERT INTO Ingredients (name, current_stock, safety_stock, unit) VALUES (?, ?, 0.0, ?)", (new_name, new_stock, new_unit))
                conn.commit()
                
                # 觸發成功狀態
                st.session_state.add_success_msg = f"✅ 已成功新增物料：{new_name}"
                st.rerun() # 重新整理畫面
            else:
                st.error("請至少輸入物料名稱！")

    # 顯示成功提示 (如果有的話)
    if st.session_state.add_success_msg:
        st.success(st.session_state.add_success_msg)
        # 顯示完畢後將狀態關閉，下次刷新時文字就會消失
        st.session_state.add_success_msg = False

    st.write("---") 
    st.subheader("❌ 刪除物料品項")
    if not df_ingredients.empty:
        with st.expander("展開以刪除不需要的物料"):
            with st.form("delete_ingredient_form"):
                del_options = {f"[{row['category']}] {row['name']} ({row['unit']})": row['id'] for _, row in df_ingredients.iterrows()}
                item_to_delete = st.selectbox("請選擇要刪除的物料", list(del_options.keys()))
                del_id = del_options[item_to_delete]
                confirm_delete = st.checkbox("我確定要永久刪除此物料")
                if st.form_submit_button("🗑️ 確認刪除"):
                    if confirm_delete:
                        c.execute("DELETE FROM Ingredients WHERE id = ?", (del_id,))
                        c.execute("DELETE FROM Product_BOM WHERE ingredient_id = ?", (del_id,))
                        conn.commit()
                        st.toast(f"🗑️ 已成功刪除物料！", icon="✅")
                        st.rerun()
                    else: st.error("請先勾選下方的確認方塊才能刪除喔！")

# ===== 頁面 2：訂單管理 (含 Google 行事曆連動與刪除功能) =====
if page == "訂單管理":
    st.subheader("📝 訂單與備料管理")
    df_prods = pd.read_sql_query("SELECT * FROM Products", conn)
    col_order, col_calc = st.columns([1, 1.2])
    
    with col_order:
        st.markdown("### 1. 新增客戶訂單")
        if df_prods.empty:
            st.warning("請先到「配方設定」頁面建立至少一款甜點品項！")
        else:
            with st.form("add_order_form", clear_on_submit=True):
                c_name = st.text_input("客戶姓名 / 訂單代號", placeholder="例如：王小姐 或 IG-001")
                d_date = st.date_input("預計交貨 / 取件日期")
                prod_options = {row['name']: row['id'] for _, row in df_prods.iterrows()}
                selected_prod = st.selectbox("訂購品項", list(prod_options.keys()))
                qty = st.number_input("訂購數量", min_value=1, step=1)
                
                if st.form_submit_button("建立訂單", use_container_width=True):
                    p_id = prod_options[selected_prod]
                    c.execute("INSERT INTO Orders (customer_name, delivery_date, product_id, quantity, status) VALUES (?, ?, ?, ?, ?)", 
                              (c_name, str(d_date), p_id, qty, '待處理'))
                    conn.commit()
                    st.toast("✅ 訂單建立成功！")
                    st.rerun()

    # ─── 3. 訂單列表與自選備料計算 ───
    st.write("---")
    
    col_list, col_calc = st.columns([1.2, 1])

    with col_list:
        st.markdown("### 📋 待處理訂單 (勾選計算)")
        
        # 🌟 先抓取所有產品清單，供「修改訂單」的下拉選單使用
        df_prods_for_edit = pd.read_sql_query("SELECT id, name FROM Products", conn)
        prod_options = {row['name']: row['id'] for _, row in df_prods_for_edit.iterrows()}
        
        # 確保有抓到 o.product_id，修改時才找得到對應的甜點
        query = """
        SELECT o.id, o.customer_name, o.delivery_date, o.quantity, o.product_id, p.name AS product_name, p.batch_yield, p.prep_days
        FROM Orders o 
        JOIN Products p ON o.product_id = p.id 
        WHERE o.status = '待處理' 
        ORDER BY o.delivery_date ASC
        """
        df_orders = pd.read_sql_query(query, conn)

        selected_orders = {}

        if df_orders.empty:
            st.caption("目前沒有待處理訂單。")
        else:
            for _, row in df_orders.iterrows():
                with st.container(border=True):
                    # 🌟 定義這張訂單專屬的「修改開關」
                    edit_key = f"edit_order_{row['id']}"
                    if edit_key not in st.session_state:
                        st.session_state[edit_key] = False

                    # ==========================================
                    # 模式 A：如果是「編輯模式」，顯示修改表單
                    # ==========================================
                    if st.session_state[edit_key]:
                        st.markdown(f"**✏️ 修改訂單 #{row['id']}**")
                        with st.form(f"form_edit_{row['id']}"):
                            # 處理預設日期
                            try:
                                default_date = datetime.strptime(str(row['delivery_date']), "%Y-%m-%d").date()
                            except ValueError:
                                default_date = datetime.today().date()
                                
                            # 處理預設選中的甜點
                            prod_names = list(prod_options.keys())
                            try:
                                default_idx = prod_names.index(row['product_name'])
                            except ValueError:
                                default_idx = 0
                                
                            new_name = st.text_input("顧客名稱", value=row['customer_name'])
                            new_date = st.date_input("交貨日期", value=default_date)
                            new_prod_name = st.selectbox("品項", prod_names, index=default_idx)
                            new_qty = st.number_input("訂購數量", min_value=1, value=int(row['quantity']))
                            
                            c_save, c_cancel = st.columns(2)
                            with c_save:
                                if st.form_submit_button("💾 儲存修改", use_container_width=True):
                                    new_prod_id = prod_options[new_prod_name]
                                    c.execute("UPDATE Orders SET customer_name=?, delivery_date=?, product_id=?, quantity=? WHERE id=?", 
                                              (new_name, str(new_date), new_prod_id, new_qty, row['id']))
                                    conn.commit()
                                    st.session_state[edit_key] = False
                                    st.toast("✅ 訂單修改成功！")
                                    st.rerun()
                            with c_cancel:
                                if st.form_submit_button("❌ 取消", use_container_width=True):
                                    st.session_state[edit_key] = False
                                    st.rerun()

                    # ==========================================
                    # 模式 B：如果是「正常模式」，顯示訂單資訊與按鈕
                    # ==========================================
                    else:
                        try:
                            delivery_date_obj = datetime.strptime(str(row['delivery_date']), "%Y-%m-%d")
                        except ValueError:
                            delivery_date_obj = datetime.today()
                            
                        prep_days = int(row['prep_days']) if pd.notna(row['prep_days']) else 0
                        prep_start_date_obj = delivery_date_obj - timedelta(days=prep_days)
                        
                        c_info, c_check = st.columns([3, 1])
                        with c_info:
                            st.write(f"**👤 {row['customer_name']}** | 📦 {row['product_name']} | 📅 交貨日：{row['delivery_date']}")
                            st.caption(f"📍 客戶訂購數量：**{row['quantity']}**")
                            
                            if prep_days > 0:
                                st.warning(f"⏳ 需提前 **{prep_days}** 天準備！建議於 **{prep_start_date_obj.strftime('%Y-%m-%d')}** 開始製作")
                            
                        with c_check:
                            is_checked = st.checkbox("🛒 計算", key=f"chk_calc_{row['id']}")
                            
                        if is_checked:
                            prod_qty = st.number_input(
                                "👉 這次實際要製作幾個？", 
                                min_value=1, 
                                value=int(row['quantity']), 
                                key=f"prod_qty_{row['id']}"
                            )
                            selected_orders[row['id']] = prod_qty
                        
                        st.write("") 
                        
                        prep_date_str = prep_start_date_obj.strftime("%Y%m%d")
                        unit_str = "份" if int(row['batch_yield']) <= 1 else "個"
                        order_qty = int(row['quantity'])
                        
                        event_title = f"📋訂單：{row['product_name']}({order_qty}{unit_str})"
                        event_details = f"顧客：{row['customer_name']}\n品項：{row['product_name']}\n數量：{order_qty}{unit_str}\n\n⚠️ 注意：此品項需提前 {prep_days} 天製作。\n📅 實際交貨日期為：{row['delivery_date']}"
                        
                        gcal_url = (
                            f"https://calendar.google.com/calendar/render?action=TEMPLATE"
                            f"&text={urllib.parse.quote(event_title)}"
                            f"&dates={prep_date_str}/{prep_date_str}" 
                            f"&details={urllib.parse.quote(event_details)}"
                        )
                        
                        # 🌟 升級為 4 個按鈕：加入了「修改」按鈕
                        btn1, btn2, btn3, btn4 = st.columns(4)
                        with btn1:
                            st.link_button("➕ 行事曆", gcal_url, use_container_width=True)
                        with btn2:
                            # 點擊修改，開啟編輯模式
                            if st.button("✏️ 修改", key=f"btn_edit_{row['id']}", use_container_width=True):
                                st.session_state[edit_key] = True
                                st.rerun()
                        with btn3:
                            if st.button("✅ 完成", key=f"finish_{row['id']}", use_container_width=True):
                                c.execute("UPDATE Orders SET status = '已完成' WHERE id = ?", (row['id'],))
                                conn.commit()
                                st.toast("🎉 訂單已完成！")
                                st.rerun()
                        with btn4:
                            del_key = f"del_order_{row['id']}"
                            if del_key not in st.session_state: st.session_state[del_key] = False
                            
                            if not st.session_state[del_key]:
                                if st.button("🗑️ 刪除", key=f"btn_init_{row['id']}", use_container_width=True):
                                    st.session_state[del_key] = True
                                    st.rerun()
                            else:
                                if st.button("🚨 確定？", key=f"btn_confirm_{row['id']}", use_container_width=True):
                                    c.execute("DELETE FROM Orders WHERE id = ?", (row['id'],))
                                    conn.commit()
                                    st.session_state[del_key] = False
                                    st.toast("🗑️ 訂單已刪除", icon="✅")
                                    st.rerun()
                                if st.button("❌ 取消", key=f"btn_cancel_{row['id']}", use_container_width=True):
                                    st.session_state[del_key] = False
                                    st.rerun()

    with col_calc:
        st.markdown("### 🧮 智慧備料與採購清單")
        
        # 判斷字典裡有沒有資料 (是否勾選了訂單)
        if not selected_orders:
            st.info("👈 請在左側勾選訂單，並可微調「實際製作量」，系統會為您精算物料！")
        else:
            order_ids = list(selected_orders.keys())
            placeholders = ','.join(['?'] * len(order_ids))
            
            # 🌟 邏輯大改寫：我們先把配方抓出來，再透過程式計算動態數量
            calc_query = f"""
            SELECT 
                o.id AS order_id,
                i.name AS 物料名稱, 
                p.batch_yield,
                b.required_quantity,
                i.current_stock AS 目前庫存, 
                i.unit AS 單位
            FROM Orders o 
            JOIN Products p ON o.product_id = p.id
            JOIN Product_BOM b ON o.product_id = b.product_id 
            JOIN Ingredients i ON b.ingredient_id = i.id
            WHERE o.id IN ({placeholders})
            """
            
            df_bom = pd.read_sql_query(calc_query, conn, params=tuple(order_ids))
            
            if df_bom.empty:
                st.warning("⚠️ 您勾選的訂單品項似乎還沒有設定配方喔！")
            else:
                # 將你輸入的「實際製作數量」映射進來
                df_bom['actual_prod_qty'] = df_bom['order_id'].map(selected_orders)
                
                # 全新計算公式：(實際製作量 / 配方預設產出量) * 配方需求量
                df_bom['需求量'] = (df_bom['actual_prod_qty'] / df_bom['batch_yield']) * df_bom['required_quantity']
                
                # 把相同物料的需求量加總起來
                df_calc = df_bom.groupby(['物料名稱', '目前庫存', '單位'])['需求量'].sum().reset_index()
                df_calc.rename(columns={'需求量': '總需求量'}, inplace=True)
                df_calc['總需求量'] = df_calc['總需求量'].round(1)
                
                # 判斷庫存狀態
                df_calc['狀態'] = df_calc.apply(
                    lambda x: '✅ 充足' if x['目前庫存'] >= x['總需求量'] else f"⚠️ 缺 {round(x['總需求量'] - x['目前庫存'], 1)}", 
                    axis=1
                )
                
                st.dataframe(
                    df_calc[['物料名稱', '總需求量', '目前庫存', '單位', '狀態']],
                    use_container_width=True,
                    hide_index=True
                )


# ===== 頁面 3：配方設定 (內建雙重防呆完美版) =====
if page == "配方設定":
    st.subheader("👩‍🍳 甜點品項與配方設定")
    
    # ─── 1. 新增甜點區塊 ───
    with st.expander("➕ 新增全新甜點品項", expanded=False):
        with st.form("add_product_form", clear_on_submit=True):
            col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
            with col1: prod_name = st.text_input("甜點名稱", placeholder="例如：經典可麗露")
            with col2: prod_price = st.number_input("販售單價", min_value=0, step=50)
            with col3: prod_prep = st.number_input("提前製作(天)", min_value=0, step=1)
            with col4: prod_yield = st.number_input("配方可做(個/份)", min_value=1, step=1, value=1, help="這份配方打出來可以做幾個？")
            with col5:
                st.write("")
                st.write("")
                submitted = st.form_submit_button("建立品項", use_container_width=True)
                
            if submitted and prod_name:
                c.execute("INSERT INTO Products (name, price, prep_days, batch_yield) VALUES (?, ?, ?, ?)", (prod_name, prod_price, prod_prep, prod_yield))
                conn.commit()
                st.session_state.selected_dessert = prod_name 
                st.toast(f"✅ 成功建立：{prod_name}")
                st.rerun()
                
    st.write("---")

    # ─── 2. 選擇目前要管理的甜點 ───
    df_prods = pd.read_sql_query("SELECT * FROM Products", conn)
    df_ing_check = pd.read_sql_query("SELECT * FROM Ingredients", conn)
    
    if df_prods.empty:
        st.info("👈 請先在上方新增第一款甜點！")
    else:
        prod_options = {row['name']: row['id'] for _, row in df_prods.iterrows()}
        if "selected_dessert" not in st.session_state or st.session_state.selected_dessert not in prod_options:
            st.session_state.selected_dessert = list(prod_options.keys())[0]

        selected_prod_name = st.selectbox("🔎 請選擇要設定或查看的甜點：", list(prod_options.keys()), index=list(prod_options.keys()).index(st.session_state.selected_dessert))
        st.session_state.selected_dessert = selected_prod_name
        
        prod_info = df_prods[df_prods['name'] == selected_prod_name].iloc[0]
        current_p_id = int(prod_info['id']) 
        current_p_price = int(prod_info['price'])
        current_p_prep = int(prod_info['prep_days']) if pd.notna(prod_info['prep_days']) else 0
        current_p_yield = int(prod_info['batch_yield']) if pd.notna(prod_info['batch_yield']) else 1

        # ─── 3. 顯示該甜點的詳細資訊與配方表 ───
        col_info, col_recipe = st.columns([1, 2])
        
        with col_info:
            st.markdown(f"### 🍰 {selected_prod_name}")
            st.write(f"**售價：** ${current_p_price}")
            st.write(f"**提前準備：** {current_p_prep} 天")
            st.write(f"**配方產量：** 每次 {current_p_yield} 個/份")
            
            # 修改面板開關
            edit_prod_key = f"edit_active_{current_p_id}"
            if edit_prod_key not in st.session_state:
                st.session_state[edit_prod_key] = False
                
            if not st.session_state[edit_prod_key]:
                if st.button("✏️ 修改甜點資訊", key=f"btn_open_{current_p_id}", use_container_width=True):
                    st.session_state[edit_prod_key] = True
                    st.rerun()
            else:
                if st.button("❌ 取消修改", key=f"btn_close_{current_p_id}", use_container_width=True):
                    st.session_state[edit_prod_key] = False
                    st.rerun()
            
            if st.session_state[edit_prod_key]:
                with st.form(f"edit_prod_form_{current_p_id}"):
                    new_name = st.text_input("新名稱", value=selected_prod_name)
                    new_price = st.number_input("新售價", value=float(current_p_price), step=10.0)
                    new_prep = st.number_input("提前製作(天)", value=current_p_prep, step=1)
                    new_yield = st.number_input("配方可做(個/份)", value=current_p_yield, min_value=1, step=1)
                    
                    if st.form_submit_button("確認儲存", use_container_width=True):
                        c.execute("UPDATE Products SET name=?, price=?, prep_days=?, batch_yield=? WHERE id=?", (new_name, new_price, new_prep, new_yield, current_p_id))
                        conn.commit()
                        st.session_state.selected_dessert = new_name
                        st.session_state[edit_prod_key] = False
                        st.toast("✅ 品項修改成功！")
                        st.rerun()
            
            st.write("") # 留一點空白間隔
            
            # 🌟 核心魔法：甜點刪除的「防呆狀態確認機制」
            del_confirm_key = f"del_confirm_{current_p_id}"
            if del_confirm_key not in st.session_state:
                st.session_state[del_confirm_key] = False
                
            if not st.session_state[del_confirm_key]:
                # 平常顯示的普通刪除按鈕
                if st.button("🗑️ 刪除此甜點", key=f"btn_del_init_{current_p_id}", use_container_width=True):
                    st.session_state[del_confirm_key] = True
                    st.rerun()
            else:
                # 點擊後觸發防呆機制，彈出警告與二次確認按鈕
                st.warning("⚠️ 是否確定刪除？（專屬配方也會同步移除且無法恢復喔！）")
                c_del1, c_del2 = st.columns(2)
                with c_del1:
                    if st.button("🚨 確定刪除", key=f"btn_del_confirm_{current_p_id}", use_container_width=True):
                        c.execute("DELETE FROM Products WHERE id=?", (current_p_id,))
                        c.execute("DELETE FROM Product_BOM WHERE product_id=?", (current_p_id,))
                        conn.commit()
                        
                        # 自動幫下拉選單切換到其他還存在的甜點
                        remaining_prods = [k for k in prod_options.keys() if prod_options[k] != current_p_id]
                        st.session_state.selected_dessert = remaining_prods[0] if remaining_prods else None
                        
                        st.session_state[del_confirm_key] = False
                        st.toast("🗑️ 品項已成功刪除！", icon="✅")
                        st.rerun()
                with c_del2:
                    if st.button("❌ 取消", key=f"btn_del_cancel_{current_p_id}", use_container_width=True):
                        st.session_state[del_confirm_key] = False
                        st.rerun()

        with col_recipe:
            st.markdown(f"### 📋 專屬配方表 (製作 {current_p_yield} 個的總量)")
            bom_query = """
            SELECT Ingredients.id AS ing_id, Ingredients.name, Product_BOM.required_quantity, Ingredients.unit
            FROM Product_BOM JOIN Ingredients ON Product_BOM.ingredient_id = Ingredients.id
            WHERE Product_BOM.product_id = ?
            """
            df_bom = pd.read_sql_query(bom_query, conn, params=(current_p_id,))
            
            if df_bom.empty: st.caption("這款甜點目前沒有配方，請從下方新增喔。")
            else:
                for _, row in df_bom.iterrows():
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 1])
                        c1.write(f"🧈 **{row['name']}** ｜ ⚖️ {row['required_quantity']} {row['unit']}")
                        with c2:
                            edit_bom_key = f"edit_bom_active_{current_p_id}_{row['ing_id']}"
                            if edit_bom_key not in st.session_state:
                                st.session_state[edit_bom_key] = False
                            
                            # 🌟 關鍵魔法：注入網頁樣式，強制讓小按鈕在手機版畫面上也不換行（保持水平排列）
                            st.markdown("""
                                <style>
                                /* 鎖定欄位內的巢狀欄位，在窄螢幕下維持橫向排列並縮小間距 */
                                div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"] {
                                    flex-direction: row !important;
                                    flex-wrap: nowrap !important;
                                    gap: 6px !important;
                                }
                                div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"] {
                                    min-width: 0px !important;
                                }
                                </style>
                            """, unsafe_allow_html=True)
                            
                            # 建立兩個子欄位
                            c_edit_btn, c_del_btn = st.columns(2)
                            
                            with c_edit_btn:
                                if not st.session_state[edit_bom_key]:
                                    if st.button("✏️ 修改", key=f"btn_bom_open_{row['ing_id']}", use_container_width=True):
                                        st.session_state[edit_bom_key] = True
                                        st.rerun()
                                else:
                                    if st.button("❌ 取消", key=f"btn_bom_close_{row['ing_id']}", use_container_width=True):
                                        st.session_state[edit_bom_key] = False
                                        st.rerun()
                                        
                            with c_del_btn:
                                if st.button("🗑️ 刪除", key=f"bdel_{row['ing_id']}", use_container_width=True):
                                    c.execute("DELETE FROM Product_BOM WHERE product_id=? AND ingredient_id=?", (current_p_id, int(row['ing_id'])))
                                    conn.commit()
                                    st.toast("🗑️ 配方已刪除！")
                                    st.rerun()
                        
                        if st.session_state[edit_bom_key]:
                            with st.form(f"edit_bom_form_{row['ing_id']}"):
                                new_qty = st.number_input("新數量", value=float(row['required_quantity']), step=5.0)
                                if st.form_submit_button("儲存", use_container_width=True):
                                    c.execute("UPDATE Product_BOM SET required_quantity=? WHERE product_id=? AND ingredient_id=?", (new_qty, current_p_id, int(row['ing_id'])))
                                    conn.commit()
                                    st.session_state[edit_bom_key] = False
                                    st.toast("✅ 配方修改成功！")
                                    st.rerun()
                                
            if not df_ing_check.empty:
                with st.form("add_bom_form", clear_on_submit=True):
                    st.write(f"➕ **加入新原料 (製作 {current_p_yield} 個所需的量)**")
                    c_ing, c_qty, c_btn = st.columns([2, 2, 1])
                    ing_options = {f"{row['name']} ({row['unit']})": row['id'] for _, row in df_ing_check.iterrows()}
                    with c_ing: selected_ing = st.selectbox("選擇原料", list(ing_options.keys()), label_visibility="collapsed")
                    with c_qty: req_qty = st.number_input("數量", min_value=0.0, step=1.0, label_visibility="collapsed", placeholder="數量")
                    with c_btn:
                        if st.form_submit_button("加入", use_container_width=True):
                            i_id = int(ing_options[selected_ing])
                            c.execute("INSERT OR REPLACE INTO Product_BOM (product_id, ingredient_id, required_quantity) VALUES (?, ?, ?)", (current_p_id, i_id, req_qty))
                            conn.commit()
                            st.toast("✅ 配方加入成功！")
                            st.rerun()


# ===== 頁面 4：成本分析 (輸入成本與檢視) =====
if page == "成本分析":
    # 🌟 萬用自我修復防禦機制：放在最前面！確保一進入此頁面，資料庫欄位絕對齊全，任何頁籤都不會閃退
    required_columns = {
        "hourly_wage": "REAL DEFAULT 183.0",
        "packaging_cost": "REAL DEFAULT 0.0",
        "production_hours": "REAL DEFAULT 0.0",
        "overhead_cost": "REAL DEFAULT 0.0",
        "production_hours_2": "REAL DEFAULT 0.0",
        "overhead_cost_2": "REAL DEFAULT 0.0",
        "production_hours_3": "REAL DEFAULT 0.0",
        "overhead_cost_3": "REAL DEFAULT 0.0"
    }
    
    c_check = conn.cursor()
    c_check.execute("PRAGMA table_info(Products)")
    existing_cols = [r[1] for r in c_check.fetchall()]
    
    db_changed = False
    for col_name, col_type in required_columns.items():
        if col_name not in existing_cols:
            try:
                c_check.execute(f'ALTER TABLE Products ADD COLUMN "{col_name}" {col_type}')
                db_changed = True
            except sqlite3.OperationalError:
                pass
    
    if db_changed:
        conn.commit()
        st.rerun()  # 補齊欄位後立即重整，確保下方所有 tabs 正常載入

    tab_ing_cost, tab_other_cost, tab_profit = st.tabs(["🛒 原物料單價設定", "📦 包材與雜支設定", "📊 利潤試算預覽"])
    
    # ─── 頁籤 1：設定原物料單價 ───
    with tab_ing_cost:
        st.markdown("### 🛒 原物料單價設定")
        st.markdown("請在這裡輸入各項原物料的**「每單位成本」**，或使用下方的快速換算工具。")
        
        # 🌟 全新加入：總量與總價快速換算計算機
        with st.expander("🧮 記不住單價？使用「總量與總價」快速換算並儲存", expanded=True):
            df_ing_calc = pd.read_sql_query("SELECT id, name, unit FROM Ingredients", conn)
            
            if df_ing_calc.empty:
                st.caption("目前沒有物料，請先到「庫存總覽」新增物料。")
            else:
                # 建立對照字典
                calc_options = {row['name']: row['id'] for _, row in df_ing_calc.iterrows()}
                calc_units = {row['name']: row['unit'] for _, row in df_ing_calc.iterrows()}
                
                # 三欄位排版：選擇物料、輸入總價、輸入總量
                col_sel, col_p, col_w = st.columns(3)
                with col_sel:
                    selected_ing_name = st.selectbox("1. 選擇要設定的物料", list(calc_options.keys()), key="calc_ing_sel")
                with col_p:
                    total_money = st.number_input("2. 購買總金額 ($)", min_value=0.0, step=1.0, value=0.0, key="calc_total_money")
                with col_w:
                    current_unit = calc_units[selected_ing_name]
                    total_qty = st.number_input(f"3. 購買總總量 ({current_unit})", min_value=0.0001, step=1.0, value=1.0, key="calc_total_qty")
                
                # 只要有輸入數字，就即時秀出換算結果
                if total_money > 0 and total_qty > 0:
                    calculated_unit_price = total_money / total_qty
                    st.success(f"💡 換算結果：每 1 {current_unit} 的單價為 **$ {calculated_unit_price:.4f}**")
                    
                    if st.button(f"💾 直接更新「{selected_ing_name}」的每單位成本", use_container_width=True, key="btn_save_calc_price"):
                        target_id = calc_options[selected_ing_name]
                        c.execute("UPDATE Ingredients SET unit_price=? WHERE id=?", (calculated_unit_price, target_id))
                        conn.commit()
                        st.toast(f"💰 已成功更新 {selected_ing_name} 單價為 $ {calculated_unit_price:.4f}！", icon="✅")
                        st.rerun()

        st.write("---")
        st.markdown("##### 📋 所有物料單價總覽 (亦可在下方表格直接修改)")
        
        # 底下保留你原本的 data_editor 表格與手動儲存按鈕
        df_ing = pd.read_sql_query("SELECT id, name, unit, unit_price FROM Ingredients", conn)
        
        if not df_ing.empty:
            with st.form("update_ing_price_form"):
                edited_df_ing = st.data_editor(
                    df_ing,
                    column_config={
                        "id": None,
                        "name": st.column_config.TextColumn("物料名稱", disabled=True),
                        "unit": st.column_config.TextColumn("單位", disabled=True),
                        "unit_price": st.column_config.NumberColumn("每單位成本 ($)", min_value=0.0, format="$ %.4f", step=0.0001)
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                if st.form_submit_button("💾 儲存下方表格內所有手動修改", use_container_width=True):
                    for _, row in edited_df_ing.iterrows():
                        c.execute("UPDATE Ingredients SET unit_price=? WHERE id=?", (row['unit_price'], row['id']))
                    conn.commit()
                    st.toast("✅ 物料單價已全面更新！", icon="💰")
                    st.rerun()

    # ─── 頁籤 2：設定甜點附加成本 (包材、雜支、時間與自訂) ───
    with tab_other_cost:
        st.markdown("### 📦 附加成本與時間設定")
        st.markdown("請選擇甜點品項，並設定 1 份、2 份、3 份的製作時間與費用。系統會自動記憶！")       
        
        # 1. 獲取所有甜點
        df_prods_all = pd.read_sql_query("SELECT * FROM Products", conn)
        
        if df_prods_all.empty:
            st.warning("目前沒有甜點品項，請先到「配方設定」新增！")
        else:
            # 手機超友善：用下拉選單挑選你要修改的甜點
            prod_names = df_prods_all['name'].tolist()
            selected_prod_name = st.selectbox("🎯 請選擇要設定的甜點", prod_names, key="edit_cost_prod_select")
            
            # 取得該甜點目前的資料庫數據
            prod_row = df_prods_all[df_prods_all['name'] == selected_prod_name].iloc[0]
            
            # 手機專屬直式表單：點擊輸入框就能直接打字修改
            with st.form(f"form_other_cost_{prod_row['id']}"):
                st.markdown(f"#### ✏️ 調整【{selected_prod_name}】的設定")
                
                # 基本費用設定 (時薪與包材)
                c_wage, c_pack = st.columns(2)
                with c_wage:
                    # 使用 get() 加上預設值，保證安全不報錯
                    val_hourly_wage = float(prod_row.get('hourly_wage', 183.0)) if pd.notna(prod_row.get('hourly_wage', 183.0)) else 183.0
                    new_hourly_wage = st.number_input("基本時薪 ($/時)", min_value=0.0, value=val_hourly_wage, step=5.0)
                with c_pack:
                    val_pack = float(prod_row.get('packaging_cost', 0.0)) if pd.notna(prod_row.get('packaging_cost', 0.0)) else 0.0
                    new_packaging_cost = st.number_input("單份包材費 ($/份)", min_value=0.0, value=val_pack, step=1.0)
                
                st.write("---")
                st.markdown("##### ⏱️ 製作時間與水電雜支設定 (核心對照組)")
                
                # 1 份設定
                st.markdown("**➡️ 製作 1 份配方：**")
                c_h1, c_o1 = st.columns(2)
                with c_h1:
                    val_h1 = float(prod_row.get('production_hours', 0.0)) if pd.notna(prod_row.get('production_hours', 0.0)) else 0.0
                    new_h1 = st.number_input("製作時間 (1份) (小時)", min_value=0.0, value=val_h1, step=0.5, key="h1")
                with c_o1:
                    val_o1 = float(prod_row.get('overhead_cost', 0.0)) if pd.notna(prod_row.get('overhead_cost', 0.0)) else 0.0
                    new_o1 = st.number_input("水電雜支 (1份) ($)", min_value=0.0, value=val_o1, step=5.0, key="o1")
                
                # 2 份設定
                st.markdown("**➡️ 製作 2 份配方 (可聯烤省時省電)：**")
                c_h2, c_o2 = st.columns(2)
                with c_h2:
                    val_h2 = float(prod_row.get('production_hours_2', 0.0)) if pd.notna(prod_row.get('production_hours_2', 0.0)) else 0.0
                    new_h2 = st.number_input("製作時間 (2份) (小時)", min_value=0.0, value=val_h2, step=0.5, key="h2")
                with c_o2:
                    val_o2 = float(prod_row.get('overhead_cost_2', 0.0)) if pd.notna(prod_row.get('overhead_cost_2', 0.0)) else 0.0
                    new_o2 = st.number_input("水電雜支 (2份) ($)", min_value=0.0, value=val_o2, step=5.0, key="o2")
                
                # 3 份設定
                st.markdown("**➡️ 製作 3 份配方 (最大產能攤提)：**")
                c_h3, c_o3 = st.columns(2)
                with c_h3:
                    val_h3 = float(prod_row.get('production_hours_3', 0.0)) if pd.notna(prod_row.get('production_hours_3', 0.0)) else 0.0
                    new_h3 = st.number_input("製作時間 (3份) (小時)", min_value=0.0, value=val_h3, step=0.5, key="h3")
                with c_o3:
                    val_o3 = float(prod_row.get('overhead_cost_3', 0.0)) if pd.notna(prod_row.get('overhead_cost_3', 0.0)) else 0.0
                    new_o3 = st.number_input("水電雜支 (3份) ($)", min_value=0.0, value=val_o3, step=5.0, key="o3")
                
                # 自動辨識是否有「自訂項目」(如：貼紙、緞帶、平台抽成)
                ignored_cols = ['id', 'name', 'price', 'prep_days', 'batch_yield', 'labor_cost', 'production_minutes', 'production_hours', 'production_hours_2', 'production_hours_3', 'overhead_cost', 'overhead_cost_2', 'overhead_cost_3', 'hourly_wage', 'packaging_cost']
                custom_cols = [col for col in df_prods_all.columns if col not in ignored_cols]
                
                new_custom_values = {}
                if custom_cols:
                    st.write("---")
                    st.markdown("##### 🏷️ 其他自訂附加項目")
                    for i in range(0, len(custom_cols), 2):
                        cols = st.columns(2)
                        for j in range(2):
                            if i + j < len(custom_cols):
                                col_name = custom_cols[i+j]
                                val_custom = float(prod_row.get(col_name, 0.0)) if pd.notna(prod_row.get(col_name, 0.0)) else 0.0
                                with cols[j]:
                                    new_custom_values[col_name] = st.number_input(f"{col_name} ($/份)", min_value=0.0, value=val_custom, step=1.0)
                
                st.write("")
                if st.form_submit_button("💾 儲存此甜點的所有成本與時間設定", use_container_width=True):
                    update_fields = {
                        "hourly_wage": new_hourly_wage,
                        "packaging_cost": new_packaging_cost,
                        "production_hours": new_h1,
                        "overhead_cost": new_o1,
                        "production_hours_2": new_h2,
                        "overhead_cost_2": new_o2,
                        "production_hours_3": new_h3,
                        "overhead_cost_3": new_o3
                    }
                    update_fields.update(new_custom_values)
                    
                    set_clauses = ", ".join([f'"{k}"=?' for k in update_fields.keys()])
                    values = list(update_fields.values()) + [int(prod_row['id'])]
                    
                    c.execute(f"UPDATE Products SET {set_clauses} WHERE id=?", values)
                    conn.commit()
                    st.toast(f"✅ 【{selected_prod_name}】所有設定已成功儲存！", icon="💾")
                    st.rerun()

        st.write("---")
        with st.expander("➕ 新增自訂成本項目 (例如：貼紙、緞帶)", expanded=False):
            col_new_name, col_new_btn = st.columns([3, 1])
            with col_new_name:
                new_cost_name = st.text_input("輸入新成本名稱", label_visibility="collapsed", placeholder="請輸入項目名稱，例如：貼紙")
            with col_new_btn:
                if st.button("新增項目", use_container_width=True):
                    if new_cost_name:
                        safe_name = new_cost_name.replace('"', '').replace("'", "").strip()
                        try:
                            c.execute(f'ALTER TABLE Products ADD COLUMN "{safe_name}" REAL DEFAULT 0.0')
                            conn.commit()
                            st.toast(f"✅ 已成功新增「{safe_name}」欄位！")
                            st.rerun()
                        except sqlite3.OperationalError:
                            st.error("⚠️ 此項目可能已經存在！")

    # ─── 頁籤 3：利潤試算預覽與多份數精算 ───
    with tab_profit:
        st.markdown("### 📊 甜點成本與利潤總覽")
        
        # 抓取 Products 表的所有欄位結構
        df_prods_all = pd.read_sql_query("SELECT * FROM Products", conn)
        
        if df_prods_all.empty:
            st.warning("目前沒有甜點品項，請先到「配方設定」新增！")
        else:
            # 🌟 智慧分類：精準定義系統與整批計算欄位，避免誤歸類為單份固定成本
            base_cols = ['id', 'name', 'price', 'prep_days', 'batch_yield', 'labor_cost', 'production_minutes']
            batch_calc_cols = ['hourly_wage', 'production_hours', 'production_hours_2', 'production_hours_3', 'overhead_cost', 'overhead_cost_2', 'overhead_cost_3']
            
            # 自動辨識真正的「每份固定成本」欄位 (如：包材費，以及您未來手動新增的貼紙、緞帶等自訂欄位)
            per_unit_cost_cols = [col for col in df_prods_all.columns if col not in base_cols + batch_calc_cols]
            
            # 使用 LEFT JOIN 抓取甜點、配方與食材的完整關聯資料
            profit_query = """
            SELECT 
                p.*,
                b.required_quantity,
                i.name AS ing_name,
                i.unit_price,
                i.unit AS ing_unit
            FROM Products p
            LEFT JOIN Product_BOM b ON p.id = b.product_id
            LEFT JOIN Ingredients i ON b.ingredient_id = i.id
            """
            df_raw = pd.read_sql_query(profit_query, conn)
            
            # 強制轉換所有成本相關欄位為數字格式，防止空白或 None 報錯
            all_numeric_cols = ['price', 'batch_yield', 'hourly_wage', 'production_hours', 'production_hours_2', 'production_hours_3', 'overhead_cost', 'overhead_cost_2', 'overhead_cost_3'] + per_unit_cost_cols
            for col in all_numeric_cols:
                if col in df_raw.columns:
                    df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce').fillna(0.0)
            
            # 計算每項原料在配方中的總花費
            df_raw['ing_total_cost'] = df_raw['required_quantity'] * df_raw['unit_price']
            df_raw['ing_total_cost'] = df_raw['ing_total_cost'].fillna(0.0)
            
            # 依照產品的所有欄位進行分組，加總原物料成本
            group_keys = [col for col in df_prods_all.columns if col not in ['labor_cost', 'production_minutes']]
            df_product_ing = df_raw.groupby(group_keys)['ing_total_cost'].sum().reset_index()
            
            # ─── 💡 基礎（製作 1 份配方）的單個成本精算 ───
            # 1. 加總每份固定的附加成本
            df_product_ing['單份包材與附加總和'] = df_product_ing[per_unit_cost_cols].sum(axis=1)
            
            # 2. 食材單份攤提 = 食材總價 / 產出量
            df_product_ing['原物料成本/份'] = (df_product_ing['ing_total_cost'] / df_product_ing['batch_yield']).fillna(0.0)
            
            # 3. 人事單份攤提 = (1份小時 * 時薪) / 產出量
            df_product_ing['人事成本/份'] = ((df_product_ing['production_hours'] * df_product_ing['hourly_wage']) / df_product_ing['batch_yield']).fillna(0.0)
            
            # 4. 水電單份攤提 = 1份水電總額 / 產出量
            df_product_ing['水電折舊/份'] = (df_product_ing['overhead_cost'] / df_product_ing['batch_yield']).fillna(0.0)
            
            # 總成本/份 = 原物料 + 人事 + 水電 + 每份固定附加
            df_product_ing['總成本/份'] = df_product_ing['原物料成本/份'] + df_product_ing['人事成本/份'] + df_product_ing['水電折舊/份'] + df_product_ing['單份包材與附加總和']
            
            # 修飾四捨五入顯示
            df_product_ing['原物料成本/份'] = df_product_ing['原物料成本/份'].round(1)
            df_product_ing['人事成本/份'] = df_product_ing['人事成本/份'].round(1)
            df_product_ing['其他附加總和/份'] = (df_product_ing['水電折舊/份'] + df_product_ing['單份包材與附加總和']).round(1)
            df_product_ing['總成本/份'] = df_product_ing['總成本/份'].round(1)
            df_product_ing['預估毛利/份'] = (df_product_ing['price'] - df_product_ing['總成本/份']).round(1)
            
            df_product_ing['毛利率 (%)'] = df_product_ing.apply(
                lambda x: round((x['預估毛利/份'] / x['price'] * 100), 1) if x['price'] > 0 else 0.0, axis=1
            )
            
            # 顯示主總覽表格 (呈現 1 份配方時的基準數據)
            df_display = df_product_ing[['name', 'price', '原物料成本/份', '人事成本/份', '其他附加總和/份', '總成本/份', '預估毛利/份', '毛利率 (%)']].rename(columns={'name': '甜點名稱', 'price': '建議售價 ($)'})
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            # ─── 🎯 多份數定價與利潤精算區 ───
            st.write("---")
            st.markdown("### 🎯 多份數定價與利潤精算機")
            st.caption("選擇甜點並設定「目標毛利率」，系統會依據您在頁籤二設定的 1 ~ 3 份真實時間與電費，為您精算應賣售價與利潤變動！")
            
            distinct_products = [n for n in df_product_ing['name'].unique() if n is not None]
            
            if distinct_products:
                c_sel, c_margin = st.columns(2)
                with c_sel:
                    selected_prod = st.selectbox("🔍 1. 請選擇甜點品項", distinct_products, key="pricing_calc_prod")
                with c_margin:
                    target_margin = st.slider("🎯 2. 設定目標毛利率 (%)", min_value=10, max_value=90, value=60, step=5, key="pricing_target_margin")
                
                prod_data = df_product_ing[df_product_ing['name'] == selected_prod].iloc[0]
                base_yield = prod_data['batch_yield']
                
                pricing_rows = []
                
                # 依序精算 1 份、2 份、3 份的精確階梯成本
                for batches in [1, 2, 3]:
                    total_items = int(base_yield * batches)
                    
                    # 智慧讀取，若為 0 則自動套用倍數做防呆機制
                    if batches == 1:
                        batch_hours = prod_data['production_hours']
                        batch_overhead = prod_data['overhead_cost']
                    elif batches == 2:
                        batch_hours = prod_data['production_hours_2'] if prod_data['production_hours_2'] > 0 else prod_data['production_hours'] * 2
                        batch_overhead = prod_data['overhead_cost_2'] if prod_data['overhead_cost_2'] > 0 else prod_data['overhead_cost'] * 2
                    elif batches == 3:
                        batch_hours = prod_data['production_hours_3'] if prod_data['production_hours_3'] > 0 else prod_data['production_hours'] * 3
                        batch_overhead = prod_data['overhead_cost_3'] if prod_data['overhead_cost_3'] > 0 else prod_data['overhead_cost'] * 3
                    
                    # 1. 階梯總成本計算
                    ing_cost = round(prod_data['ing_total_cost'] * batches, 1) # 食材呈線性增長
                    labor_cost = round(batch_hours * prod_data['hourly_wage'], 1) # 人事依真實小時計算
                    
                    # 附加總成本 = 真實批次水電總額 + (單份包材附加固定總和 * 總件量)
                    extra_cost = round(batch_overhead + (prod_data['單份包材與附加總和'] * total_items), 1)
                    
                    # 本次總成本
                    total_cost = round(ing_cost + labor_cost + extra_cost, 1)
                    
                    # 2. 定價公式推算 (應賣金額 = 總成本 / (1 - 毛利率%))
                    suggested_total_revenue = round(total_cost / (1 - target_margin / 100), 0)
                    suggested_unit_price = round(suggested_total_revenue / total_items, 0) if total_items > 0 else 0
                    total_profit = round(suggested_total_revenue - total_cost, 0)
                    
                    pricing_rows.append({
                        "製作規模": f"製作 {batches} 份配方",
                        "預計總產出": f"{total_items} 個/份",
                        "食材總成本": f"$ {ing_cost}",
                        "人事總成本": f"$ {labor_cost}",
                        "附加總成本": f"$ {extra_cost}",
                        "總成本 (A)": f"$ {total_cost}",
                        "應賣總金額 (B)": f"$ {int(suggested_total_revenue)}",
                        "單個應賣售價": f"$ {int(suggested_unit_price)}",
                        "預估最後總利潤 (B-A)": f"$ {int(total_profit)}"
                    })
                
                df_pricing = pd.DataFrame(pricing_rows)
                
                st.write("")
                st.markdown(f"📊 **【 {selected_prod} 】1 ~ 3 份配方階梯定價對照表** (目標毛利率：{target_margin}%)")
                st.dataframe(df_pricing, use_container_width=True, hide_index=True)
                st.caption(f"💡 商業小提醒：當製作份數增加到 2 份或 3 份時，由於您在頁籤二設定的電費與時間並未翻倍（實現聯烤攤提），您會發現「單個應賣售價」明顯下降，且「預估最後總利潤」大幅跳水成長！這就是您設計限量多入組、團購優惠的最佳定價科學依據。")