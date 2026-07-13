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
              product_id INTEGER, quantity INTEGER, status TEXT)''')

# 🌟 魔法升級：安全地為現有的 Products 表格加上「提前準備天數 (prep_days)」欄位
# 🌟 魔法升級：安全地為現有的 Products 表格加上「提前準備天數」與「配方產出量」欄位
try:
    c.execute("ALTER TABLE Products ADD COLUMN prep_days INTEGER DEFAULT 0")
except sqlite3.OperationalError:
    pass 
try:
    c.execute("ALTER TABLE Products ADD COLUMN batch_yield INTEGER DEFAULT 1")
    conn.commit()
except sqlite3.OperationalError:
    pass # 如果欄位已經存在，就會默默略過，不會報錯

# 網頁介面設計
st.set_page_config(page_title="甜點工作室管理系統", page_icon="🍰", layout="wide", initial_sidebar_state="auto")
st.title("🍰 甜點工作室管理後台")

st.sidebar.header("功能選單")
page = st.sidebar.radio("請選擇頁面", ["庫存總覽", "訂單管理", "配方設定"])

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

        st.write("---")
        st.markdown("### 2. 待處理訂單清單")
        # 讀取訂單時，一併抓出該甜點需要的「提前準備天數」
        pending_query = """
        SELECT o.id, o.delivery_date AS 交期, o.customer_name AS 客戶, 
               p.name AS 品項, o.quantity AS 數量, p.prep_days
        FROM Orders o JOIN Products p ON o.product_id = p.id
        WHERE o.status = '待處理' ORDER BY o.delivery_date ASC
        """
        df_pending = pd.read_sql_query(pending_query, conn)
        
        if df_pending.empty:
            st.info("目前沒有待處理的訂單！")
        else:
            for _, row in df_pending.iterrows():
                with st.container(border=True):
                    # 計算應該在哪一天開始製作
                    delivery_dt = datetime.strptime(row['交期'], '%Y-%m-%d')
                    prep_days = int(row['prep_days']) if pd.notna(row['prep_days']) else 0
                    start_dt = delivery_dt - timedelta(days=prep_days)
                    
                    st.write(f"👤 **{row['客戶']}** ｜ 交期：{row['交期']}")
                    st.write(f"🍰 **{row['品項']}** x {row['數量']}")
                    
                    # 如果需要提前準備，顯示紅字提醒
                    if prep_days > 0:
                        st.markdown(f"⏳ <span style='color: #ff4b4b; font-weight: bold;'>請於 {start_dt.strftime('%Y-%m-%d')} 開始準備/製作！</span>", unsafe_allow_html=True)
                    else:
                        st.caption(f"這項甜點不需提前，當天 ({row['交期']}) 製作即可。")
                    
                    # 產生 Google 行事曆專屬連結
                    end_dt = start_dt + timedelta(days=1)
                    event_title = f"📋{row['品項']} ({row['數量']}份)"
                    event_details = f"客戶：{row['客戶']}\n交件日期：{row['交期']}"
                    
                    gcal_url = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={urllib.parse.quote(event_title)}&dates={start_dt.strftime('%Y%m%d')}/{end_dt.strftime('%Y%m%d')}&details={urllib.parse.quote(event_details)}"
                    
                    # 🌟 關鍵改動：切成三個等寬直排，並將按鈕文字微調精簡，確保手機與電腦上都不會擠壓換行
                    btn1, btn2, btn3 = st.columns(3)
                    with btn1:
                        st.link_button("📅 行事曆", gcal_url, use_container_width=True)
                    with btn2:
                        if st.button("✅ 完成", key=f"finish_{row['id']}", use_container_width=True):
                            c.execute("UPDATE Orders SET status = '已完成' WHERE id = ?", (row['id'],))
                            conn.commit()
                            st.toast("🎉 訂單已完成！")
                            st.rerun()
                    with btn3:
                        # 1. 定義這張訂單專屬的防呆開關 Key
                        del_order_key = f"del_order_confirm_{row['id']}"
                        if del_order_key not in st.session_state:
                            st.session_state[del_order_key] = False

                        # 2. 判斷狀態：若未按過，顯示刪除鍵；若按過，顯示確認/取消
                        if not st.session_state[del_order_key]:
                            if st.button("🗑️ 刪除", key=f"del_{row['id']}", use_container_width=True):
                                st.session_state[del_order_key] = True
                                st.rerun()
                        else:
                            # 當進入防呆模式時，我們需要跳出提示，所以必須放在容器外或是使用 st.warning
                            # 但為了版面精簡，這裡點擊刪除後，該行會變成確認按鈕
                            if st.button("🚨 確定？", key=f"del_confirm_{row['id']}", use_container_width=True):
                                c.execute("DELETE FROM Orders WHERE id=?", (int(row['id']),))
                                conn.commit()
                                st.session_state[del_order_key] = False
                                st.toast(f"🗑️ 訂單已刪除", icon="✅")
                                st.rerun()
                            if st.button("❌ 取消", key=f"del_cancel_{row['id']}", use_container_width=True):
                                st.session_state[del_order_key] = False
                                st.rerun()

    with col_calc:
        st.markdown("### 🛒 智慧備料與採購清單")
        if df_pending.empty:
            st.success("目前無待處理訂單，不需額外備料！")
        else:
            # 🌟 備料公式大升級：(訂單數量 / 配方預設產出量) * 配方需求量
            calc_query = """
            SELECT 
                i.name AS 物料名稱, 
                ROUND(SUM((o.quantity * 1.0 / p.batch_yield) * b.required_quantity), 1) AS 總需求量,
                i.current_stock AS 目前庫存, 
                i.unit AS 單位
            FROM Orders o 
            JOIN Products p ON o.product_id = p.id
            JOIN Product_BOM b ON o.product_id = b.product_id 
            JOIN Ingredients i ON b.ingredient_id = i.id
            WHERE o.status = '待處理' 
            GROUP BY i.id, i.name, i.current_stock, i.unit
            """
            df_calc = pd.read_sql_query(calc_query, conn)
            if df_calc.empty:
                st.warning("目前的訂單似乎還沒有設定配方，請先至「配方設定」綁定喔！")
            else:
                df_calc['缺口數量'] = df_calc['總需求量'] - df_calc['目前庫存']
                df_shortage = df_calc[df_calc['缺口數量'] > 0]
                df_enough = df_calc[df_calc['缺口數量'] <= 0]
                
                if not df_shortage.empty:
                    st.error("🚨 **以下物料庫存不足，請盡速採購！**")
                    for _, row in df_shortage.iterrows():
                        with st.container(border=True):
                            st.write(f"**{row['物料名稱']}**")
                            c1, c2, c3 = st.columns(3)
                            c1.metric("總需求", f"{row['總需求量']} {row['單位']}")
                            c2.metric("目前庫存", f"{row['目前庫存']} {row['單位']}")
                            c3.metric("還缺少", f"{row['缺口數量']} {row['單位']}", delta=f"-{row['缺口數量']}", delta_color="inverse")
                else:
                    st.success("✅ **目前庫存充足，可以應付所有訂單！**")

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
                                
                            if not st.session_state[edit_bom_key]:
                                if st.button("✏️ 修改", key=f"btn_bom_open_{row['ing_id']}", use_container_width=True):
                                    st.session_state[edit_bom_key] = True
                                    st.rerun()
                            else:
                                if st.button("❌ 取消", key=f"btn_bom_close_{row['ing_id']}", use_container_width=True):
                                    st.session_state[edit_bom_key] = False
                                    st.rerun()
                                    
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