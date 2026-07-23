import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import urllib.parse
from streamlit_calendar import calendar
from streamlit_gsheets import GSheetsConnection

# 網頁介面設計 (放在最前面)
st.set_page_config(page_title="甜點工作室管理系統", page_icon="🍰", layout="wide", initial_sidebar_state="auto")

# ==========================================
# 1. 建立並連線到 Google Sheets
# ==========================================
# ⚠️ 請替換為您的 Google 試算表完整網址
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1fTxkzjb5chyVh92M2ctWmiNb35YOBqikJlpNW0XKdTo/edit?gid=773310131#gid=773310131"
conn = st.connection("gsheets", type=GSheetsConnection)

# ==========================================
# 2. 讀取與初始化資料 (具備自動修復缺漏欄位機制)
# ==========================================
@st.cache_data(ttl=5)
def load_data():
    # 讀取 Ingredients
    try:
        df_ingredients = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Ingredients")
        if df_ingredients.empty: raise ValueError
    except:
        df_ingredients = pd.DataFrame(columns=["id", "name", "current_stock", "safety_stock", "unit", "unit_price"])
        
    # 讀取 Products
    try:
        df_products = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Products")
        if df_products.empty: raise ValueError
    except:
        df_products = pd.DataFrame(columns=[
            "id", "name", "price", "prep_days", "batch_yield", 
            "packaging_cost", "overhead_cost", "overhead_cost_2", "overhead_cost_3", 
            "labor_cost", "hourly_wage", "production_minutes", 
            "production_hours", "production_hours_2", "production_hours_3"
        ])
        
    # 讀取 Product_BOM
    try:
        df_bom = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Product_BOM")
        if df_bom.empty: raise ValueError
    except:
        df_bom = pd.DataFrame(columns=["product_id", "ingredient_id", "required_quantity"])
        
    # 讀取 Orders
    try:
        df_orders = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Orders")
        if df_orders.empty: raise ValueError
    except:
        df_orders = pd.DataFrame(columns=["id", "customer_name", "delivery_date", "product_id", "quantity", "status"])

    # 確保 ID 欄位為數值型態，避免後續關聯錯誤
    for df in [df_ingredients, df_products, df_bom, df_orders]:
        if 'id' in df.columns:
            df['id'] = pd.to_numeric(df['id'], errors='coerce')
        if 'product_id' in df.columns:
            df['product_id'] = pd.to_numeric(df['product_id'], errors='coerce')
        if 'ingredient_id' in df.columns:
            df['ingredient_id'] = pd.to_numeric(df['ingredient_id'], errors='coerce')

    return df_ingredients, df_products, df_bom, df_orders

df_ingredients, df_products, df_bom, df_orders = load_data()

st.title("🍰 甜點工作室管理後台")
st.sidebar.header("功能選單")
page = st.sidebar.radio("請選擇頁面", ["庫存總覽", "訂單管理", "配方設定", "成本分析"])

# 在 st.title 之後加入
if st.button("🔄 同步 Google Sheets 最新資料"):
    st.cache_data.clear() # 強制清除所有快取
    st.rerun()           # 重新載入頁面
    
# ===== 頁面 1：庫存總覽 =====
if page == "庫存總覽":
    st.subheader("📦 目前物料庫存")
    
    # 模擬 SQL 的 CASE WHEN 分類
    def get_category(name):
        if '粉' in str(name): return '粉類'
        elif '糖' in str(name): return '糖類'
        else: return '其他'
        
    if not df_ingredients.empty:
        df_ingredients['category'] = df_ingredients['name'].apply(get_category)
    
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
                                
                                current_val = float(row['current_stock'])
                                if mode == "進貨 (+)": new_val = current_val + amt
                                elif mode == "消耗 (-)": new_val = current_val - amt
                                else: new_val = amt
                                
                                # 更新 DataFrame 並寫回 GSheets
                                df_ingredients.loc[df_ingredients['id'] == row['id'], 'current_stock'] = new_val
                                conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Ingredients", data=df_ingredients)
                                st.cache_data.clear()
                                
                                st.toast(f"✨ {row['name']} 庫存更新成功！", icon="💾")
                                st.rerun()

        with tab_all: draw_inventory_cards(df_ingredients, "all")
        with tab_flour: draw_inventory_cards(df_ingredients[df_ingredients['category'] == '粉類'], "flour")
        with tab_sugar: draw_inventory_cards(df_ingredients[df_ingredients['category'] == '糖類'], "sugar")
        with tab_other: draw_inventory_cards(df_ingredients[df_ingredients['category'] == '其他'], "other")

    st.write("---")
    st.subheader("➕ 新增原物料品項")
    
    if "add_success_msg" not in st.session_state:
        st.session_state.add_success_msg = False

    with st.form("add_ingredient_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1: new_name = st.text_input("物料名稱", placeholder="例如：低筋麵粉")
        with col2: new_stock = st.number_input("初始庫存", min_value=0.0, step=100.0)
        with col3: new_unit = st.text_input("單位", placeholder="例如：g")
        
        if st.form_submit_button("新增品項"):
            if new_name:
                new_id = int(df_ingredients['id'].max() + 1) if not df_ingredients.empty else 1
                new_row = pd.DataFrame([{
                    "id": new_id, "name": new_name, "current_stock": new_stock, 
                    "safety_stock": 0.0, "unit": new_unit, "unit_price": 0.0
                }])
                
                df_updated = pd.concat([df_ingredients, new_row], ignore_index=True)
                conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Ingredients", data=df_updated)
                st.cache_data.clear()
                
                st.session_state.add_success_msg = f"✅ 已成功新增物料：{new_name}"
                st.rerun()
            else:
                st.error("請至少輸入物料名稱！")

    if st.session_state.add_success_msg:
        st.success(st.session_state.add_success_msg)
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
                        # 從 Ingredients 刪除
                        df_ingredients_clean = df_ingredients[df_ingredients['id'] != del_id]
                        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Ingredients", data=df_ingredients_clean)
                        # 從 BOM 刪除
                        df_bom_clean = df_bom[df_bom['ingredient_id'] != del_id]
                        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Product_BOM", data=df_bom_clean)
                        
                        st.cache_data.clear()
                        st.toast(f"🗑️ 已成功刪除物料！", icon="✅")
                        st.rerun()
                    else: 
                        st.error("請先勾選下方的確認方塊才能刪除喔！")

# ===== 頁面 2：訂單管理 =====
if page == "訂單管理":
    st.subheader("📝 訂單與備料管理")
    col_order, col_calc = st.columns([1, 1.2])
    
    with col_order:
        st.markdown("### 1. 新增客戶訂單")
        if df_products.empty:
            st.warning("請先到「配方設定」頁面建立至少一款甜點品項！")
        else:
            with st.form("add_order_form", clear_on_submit=True):
                c_name = st.text_input("客戶姓名 / 訂單代號", placeholder="例如：王小姐 或 IG-001")
                d_date = st.date_input("預計交貨 / 取件日期")
                prod_options = {row['name']: row['id'] for _, row in df_products.iterrows()}
                selected_prod = st.selectbox("訂購品項", list(prod_options.keys()))
                qty = st.number_input("訂購數量", min_value=1, step=1)
                
                if st.form_submit_button("建立訂單", use_container_width=True):
                    p_id = prod_options[selected_prod]
                    new_id = int(df_orders['id'].max() + 1) if not df_orders.empty else 1
                    
                    new_order = pd.DataFrame([{
                        "id": new_id, "customer_name": c_name, "delivery_date": str(d_date), 
                        "product_id": p_id, "quantity": qty, "status": '待處理'
                    }])
                    
                    df_orders_updated = pd.concat([df_orders, new_order], ignore_index=True)
                    conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Orders", data=df_orders_updated)
                    st.cache_data.clear()
                    
                    st.toast("✅ 訂單建立成功！")
                    st.rerun()

    st.write("---")
    col_list, col_calc = st.columns([1.2, 1])

    with col_list:
        st.markdown("### 📋 待處理訂單 (勾選計算)")
        
        # 篩選待處理訂單並與產品資料 Merge (已修正 name_prod 問題)
        if not df_orders.empty:
            df_pending = df_orders[df_orders['status'] == '待處理']
            df_display_orders = pd.merge(
                df_pending, 
                df_products[['id', 'name', 'batch_yield', 'prep_days']], 
                left_on='product_id', 
                right_on='id', 
                suffixes=('', '_prod')
            ).rename(columns={'name': 'name_prod'}) # 強制命名確保不出錯
            df_display_orders = df_display_orders.sort_values(by='delivery_date')
        else:
            df_display_orders = pd.DataFrame()

        selected_orders = {}

        if df_display_orders.empty:
            st.caption("目前沒有待處理訂單。")
        else:
            prod_options = {row['name']: row['id'] for _, row in df_products.iterrows()}
            
            for _, row in df_display_orders.iterrows():
                with st.container(border=True):
                    edit_key = f"edit_order_{row['id']}"
                    if edit_key not in st.session_state:
                        st.session_state[edit_key] = False

                    # ----- 編輯模式 -----
                    if st.session_state[edit_key]:
                        st.markdown(f"**✏️ 修改訂單 #{row['id']}**")
                        with st.form(f"form_edit_{row['id']}"):
                            try:
                                default_date = datetime.strptime(str(row['delivery_date']), "%Y-%m-%d").date()
                            except:
                                default_date = datetime.today().date()
                                
                            prod_names = list(prod_options.keys())
                            try:
                                default_idx = prod_names.index(row['name_prod'])
                            except ValueError:
                                default_idx = 0
                                
                            new_name = st.text_input("顧客名稱", value=row['customer_name'])
                            new_date = st.date_input("交貨日期", value=default_date)
                            new_prod_name = st.selectbox("品項", prod_names, index=default_idx)
                            new_qty = st.number_input("訂購數量", min_value=1, value=int(row['quantity']))
                            
                            c_save, c_cancel = st.columns(2)
                            with c_save:
                                if st.form_submit_button("💾 儲存", use_container_width=True):
                                    new_prod_id = prod_options[new_prod_name]
                                    idx = df_orders.index[df_orders['id'] == row['id']].tolist()[0]
                                    df_orders.at[idx, 'customer_name'] = new_name
                                    df_orders.at[idx, 'delivery_date'] = str(new_date)
                                    df_orders.at[idx, 'product_id'] = new_prod_id
                                    df_orders.at[idx, 'quantity'] = new_qty
                                    
                                    conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Orders", data=df_orders)
                                    st.cache_data.clear()
                                    st.session_state[edit_key] = False
                                    st.toast("✅ 訂單修改成功！")
                                    st.rerun()
                            with c_cancel:
                                if st.form_submit_button("❌ 取消", use_container_width=True):
                                    st.session_state[edit_key] = False
                                    st.rerun()
                                    
                    # ----- 一般顯示模式 -----
                    else:
                        try:
                            delivery_date_obj = datetime.strptime(str(row['delivery_date']), "%Y-%m-%d")
                        except:
                            delivery_date_obj = datetime.today()
                            
                        prep_days = int(row['prep_days']) if pd.notna(row['prep_days']) else 0
                        prep_start_date_obj = delivery_date_obj - timedelta(days=prep_days)
                        
                        c_info, c_check = st.columns([3, 1])
                        with c_info:
                            st.write(f"**👤 {row['customer_name']}** | 📦 {row['name_prod']} | 📅 交貨日：{row['delivery_date']}")
                            st.caption(f"📍 客戶訂購數量：**{row['quantity']}**")
                            if prep_days > 0:
                                st.warning(f"⏳ 需提前 **{prep_days}** 天準備！建議於 **{prep_start_date_obj.strftime('%Y-%m-%d')}** 開始")
                        
                        with c_check:
                            is_checked = st.checkbox("🛒 計算", key=f"chk_calc_{row['id']}")
                            if is_checked:
                                prod_qty = st.number_input("👉 實際製作量？", min_value=1, value=int(row['quantity']), key=f"prod_qty_{row['id']}")
                                selected_orders[row['id']] = prod_qty
                        
                        st.write("") 
                        prep_date_str = prep_start_date_obj.strftime("%Y%m%d")
                        unit_str = "份" if int(row['batch_yield']) <= 1 else "個"
                        order_qty = int(row['quantity'])
                        
                        event_title = f"📋訂單：{row['name_prod']}({order_qty}{unit_str})"
                        event_details = f"顧客：{row['customer_name']}\n品項：{row['name_prod']}\n數量：{order_qty}{unit_str}\n\n⚠️ 此品項需提前 {prep_days} 天製作。\n📅 交貨日：{row['delivery_date']}"
                        
                        # 處理 urllib (若最上方未 import urllib.parse，這裡也能運作)
                        import urllib.parse
                        gcal_url = (f"https://calendar.google.com/calendar/render?action=TEMPLATE"
                                    f"&text={urllib.parse.quote(event_title)}"
                                    f"&dates={prep_date_str}/{prep_date_str}" 
                                    f"&details={urllib.parse.quote(event_details)}")
                        
                        # ----- 操作按鈕 -----
                        btn1, btn2, btn3, btn4 = st.columns(4)
                        with btn1: st.link_button("➕ 行事曆", gcal_url, use_container_width=True)
                        with btn2:
                            if st.button("✏️ 修改", key=f"btn_edit_{row['id']}", use_container_width=True):
                                st.session_state[edit_key] = True
                                st.rerun()
                        with btn3:
                            if st.button("✅ 完成", key=f"finish_{row['id']}", use_container_width=True):
                                df_orders.loc[df_orders['id'] == row['id'], 'status'] = '已完成'
                                conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Orders", data=df_orders)
                                st.cache_data.clear()
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
                                    df_orders_clean = df_orders[df_orders['id'] != row['id']]
                                    conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Orders", data=df_orders_clean)
                                    st.cache_data.clear()
                                    st.session_state[del_key] = False
                                    st.toast("🗑️ 訂單已刪除", icon="✅")
                                    st.rerun()
                                if st.button("❌ 取消", key=f"btn_cancel_{row['id']}", use_container_width=True):
                                    st.session_state[del_key] = False
                                    st.rerun()

    # ----- 智慧備料與採購清單 -----
    with col_calc:
        st.markdown("### 🧮 智慧備料與採購清單")
        if not selected_orders:
            st.info("👈 請在左側勾選訂單，並可微調「實際製作量」，系統會為您精算物料！")
        else:
            order_ids = list(selected_orders.keys())
            df_o = df_orders[df_orders['id'].isin(order_ids)][['id', 'product_id']].rename(columns={'id': 'order_id'})
            df_p = df_products[['id', 'batch_yield']].rename(columns={'id': 'product_id'})
            
            m1 = pd.merge(df_o, df_p, on='product_id', how='inner')
            m2 = pd.merge(m1, df_bom, on='product_id', how='inner')
            df_i = df_ingredients[['id', 'name', 'current_stock', 'unit']].rename(columns={'id': 'ingredient_id', 'name': '物料名稱', 'current_stock': '目前庫存', 'unit': '單位'})
            df_bom_calc = pd.merge(m2, df_i, on='ingredient_id', how='inner')
            
            if df_bom_calc.empty:
                st.warning("⚠️ 您勾選的訂單品項似乎還沒有設定配方喔！")
            else:
                df_bom_calc['actual_prod_qty'] = df_bom_calc['order_id'].map(selected_orders)
                df_bom_calc['需求量'] = (df_bom_calc['actual_prod_qty'] / df_bom_calc['batch_yield']) * df_bom_calc['required_quantity']
                
                df_calc = df_bom_calc.groupby(['物料名稱', '目前庫存', '單位'])['需求量'].sum().reset_index()
                df_calc.rename(columns={'需求量': '總需求量'}, inplace=True)
                df_calc['總需求量'] = df_calc['總需求量'].round(1)
                
                df_calc['狀態'] = df_calc.apply(
                    lambda x: '✅ 充足' if float(x['目前庫存']) >= float(x['總需求量']) else f"⚠️ 缺 {round(float(x['總需求量']) - float(x['目前庫存']), 1)}", 
                    axis=1
                )
                st.dataframe(df_calc[['物料名稱', '總需求量', '目前庫存', '單位', '狀態']], use_container_width=True, hide_index=True)
    
    # ===== 新增功能：歷史訂單與利潤結算 =====
    st.write("---")
    with st.expander("✅ 已完成訂單與利潤紀錄", expanded=False):
        df_completed = df_orders[df_orders['status'] == '已完成'].copy()
        
        if df_completed.empty:
            st.info("目前還沒有已完成的訂單喔！完成訂單後會自動在這裡結算利潤。")
        else:
            import math
            
            # --- 1. 計算每個產品的單件開銷與單盒包裝費 ---
            df_bom_price = pd.merge(df_bom, df_ingredients[['id', 'unit_price']], left_on='ingredient_id', right_on='id', how='left')
            df_bom_price['required_quantity'] = pd.to_numeric(df_bom_price['required_quantity'], errors='coerce').fillna(0)
            df_bom_price['unit_price'] = pd.to_numeric(df_bom_price['unit_price'], errors='coerce').fillna(0)
            df_bom_price['ing_cost'] = df_bom_price['required_quantity'] * df_bom_price['unit_price']
            prod_cost_sum = df_bom_price.groupby('product_id')['ing_cost'].sum().reset_index()
            
            prod_info = pd.merge(df_products, prod_cost_sum, left_on='id', right_on='product_id', how='left')
            prod_info['ing_cost'] = prod_info['ing_cost'].fillna(0)
            prod_info['batch_yield'] = pd.to_numeric(prod_info['batch_yield'], errors='coerce').fillna(1)
            prod_info['price'] = pd.to_numeric(prod_info['price'], errors='coerce').fillna(0)
            
            # 確保有入數欄位，沒有的話預設為 1
            if 'items_per_box' not in prod_info.columns:
                prod_info['items_per_box'] = 1
            prod_info['items_per_box'] = pd.to_numeric(prod_info['items_per_box'], errors='coerce').fillna(1)
            
            for col in ['hourly_wage', 'production_hours', 'overhead_cost']:
                if col not in prod_info.columns: prod_info[col] = 0.0
                else: prod_info[col] = pd.to_numeric(prod_info[col], errors='coerce').fillna(0.0)
            
            # 分離附加成本
            base_cols = ['id', 'name', 'price', 'prep_days', 'batch_yield', 'labor_cost', 'production_minutes', 'target_margin', 'items_per_box']
            batch_calc_cols = ['hourly_wage', 'production_hours', 'production_hours_2', 'production_hours_3', 'overhead_cost', 'overhead_cost_2', 'overhead_cost_3', 'product_id', 'ing_cost']
            per_unit_cost_cols = [col for col in prod_info.columns if col not in base_cols + batch_calc_cols]
            
            for col in per_unit_cost_cols:
                prod_info[col] = pd.to_numeric(prod_info[col], errors='coerce').fillna(0.0)
            
            # 計算基本單位開銷
            prod_info['單份食材'] = prod_info.apply(lambda x: x['ing_cost'] / x['batch_yield'] if x['batch_yield'] > 0 else 0, axis=1)
            prod_info['單份人事'] = prod_info.apply(lambda x: (x['production_hours'] * x['hourly_wage']) / x['batch_yield'] if x['batch_yield'] > 0 else 0, axis=1)
            prod_info['單份水電'] = prod_info.apply(lambda x: x['overhead_cost'] / x['batch_yield'] if x['batch_yield'] > 0 else 0, axis=1)
            prod_info['單盒包材附加'] = prod_info[per_unit_cost_cols].sum(axis=1)
            
            # --- 2. 結算歷史訂單 (套用盒數邏輯) ---
            df_history = pd.merge(df_completed, prod_info[['id', 'name', 'price', '單份食材', '單份人事', '單份水電', '單盒包材附加', 'items_per_box']], left_on='product_id', right_on='id', how='left')
            df_history['quantity'] = pd.to_numeric(df_history['quantity'], errors='coerce').fillna(0)
            
            df_history['總營收'] = df_history['quantity'] * df_history['price']
            
            # 🌟 核心：算出這筆訂單需要幾個包裝盒 (無條件進位)
            df_history['實際盒數'] = df_history.apply(lambda x: math.ceil(x['quantity'] / x['items_per_box']) if x['items_per_box'] > 0 else 1, axis=1)
            
            # 🌟 總成本 = (食材+人事+水電) × 總顆數 + (單盒包裝費 × 實際盒數)
            df_history['總成本'] = ((df_history['單份食材'] + df_history['單份人事'] + df_history['單份水電']) * df_history['quantity']) + (df_history['單盒包材附加'] * df_history['實際盒數'])
            
            df_history['淨利潤'] = df_history['總營收'] - df_history['總成本']
            
            df_display_history = df_history[['id_x', 'customer_name', 'delivery_date', 'name', 'quantity', '實際盒數', '總營收', '總成本', '淨利潤']].copy()
            df_display_history.columns = ['訂單編號', '顧客名稱', '交貨日期', '品項', '總顆數', '消耗盒數', '總營收', '總成本(全含)', '淨利潤']
            
            df_display_history['總成本(全含)'] = df_display_history['總成本(全含)'].round(1)
            df_display_history['淨利潤'] = df_display_history['淨利潤'].round(1)
            
            st.dataframe(df_display_history, use_container_width=True, hide_index=True)
            
            # --- 3. 顯示總結算數據 ---
            total_revenue = df_display_history['總營收'].sum()
            total_profit = df_display_history['淨利潤'].sum()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("📦 累積完成訂單數", f"{len(df_display_history)} 筆")
            c2.metric("💰 累積總營收", f"${total_revenue:,.0f}")
            c3.metric("📈 累積淨利潤 (全含)", f"${total_profit:,.0f}")
            
            # --- 4. 復原訂單狀態功能 ---
            st.write("---")
            st.markdown("#### ↩️ 復原訂單狀態")
            col_rev1, col_rev2 = st.columns([2, 1])
            with col_rev1:
                rev_options = df_display_history.apply(lambda x: f"訂單 #{x['訂單編號']} - {x['顧客名稱']} ({x['品項']})", axis=1).tolist()
                rev_id_list = df_display_history['訂單編號'].tolist()
                selected_rev_index = st.selectbox("請選擇要退回「待處理」的訂單：", range(len(rev_options)), format_func=lambda i: rev_options[i])
            with col_rev2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("↩️ 恢復為「待處理」", use_container_width=True):
                    if rev_id_list:
                        rev_target_id = rev_id_list[selected_rev_index]
                        df_orders.loc[df_orders['id'] == rev_target_id, 'status'] = '待處理'
                        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Orders", data=df_orders)
                        st.cache_data.clear()
                        st.toast(f"✅ 訂單 #{rev_target_id} 已恢復為待處理！")
                        st.rerun()


# ===== 頁面 3：配方設定 =====
if page == "配方設定":
    st.subheader("👩‍🍳 甜點品項與配方設定")
    
    with st.expander("➕ 新增全新甜點品項", expanded=False):
        with st.form("add_product_form", clear_on_submit=True):
            col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
            with col1: prod_name = st.text_input("甜點名稱", placeholder="例如：經典可麗露")
            with col2: prod_price = st.number_input("販售單價", min_value=0, step=50)
            with col3: prod_prep = st.number_input("提前製作(天)", min_value=0, step=1)
            with col4: prod_yield = st.number_input("配方可做(個/份)", min_value=1, step=1, value=1)
            with col5:
                st.write("")
                st.write("")
                submitted = st.form_submit_button("建立品項", use_container_width=True)
                
            if submitted and prod_name:
                new_id = int(df_products['id'].max() + 1) if not df_products.empty else 1
                new_prod = pd.DataFrame([{
                    "id": new_id, "name": prod_name, "price": prod_price, 
                    "prep_days": prod_prep, "batch_yield": prod_yield
                }])
                df_products_updated = pd.concat([df_products, new_prod], ignore_index=True)
                conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Products", data=df_products_updated)
                st.cache_data.clear()
                
                st.session_state.selected_dessert = prod_name 
                st.toast(f"✅ 成功建立：{prod_name}")
                st.rerun()
                
    st.write("---")

    if df_products.empty:
        st.info("👈 請先在上方新增第一款甜點！")
    else:
        prod_options = {row['name']: row['id'] for _, row in df_products.iterrows()}
        if "selected_dessert" not in st.session_state or st.session_state.selected_dessert not in prod_options:
            st.session_state.selected_dessert = list(prod_options.keys())[0]

        selected_prod_name = st.selectbox("🔎 請選擇要設定或查看的甜點：", list(prod_options.keys()), index=list(prod_options.keys()).index(st.session_state.selected_dessert))
        st.session_state.selected_dessert = selected_prod_name
        
        prod_info = df_products[df_products['name'] == selected_prod_name].iloc[0]
        current_p_id = int(prod_info['id']) 
        current_p_price = int(prod_info['price']) if pd.notna(prod_info['price']) else 0
        current_p_prep = int(prod_info['prep_days']) if pd.notna(prod_info['prep_days']) else 0
        current_p_yield = int(prod_info['batch_yield']) if pd.notna(prod_info['batch_yield']) else 1

        col_info, col_recipe = st.columns([1, 2])
        
        with col_info:
            st.markdown(f"### 🍰 {selected_prod_name}")
            st.write(f"**售價：** ${current_p_price}")
            st.write(f"**提前準備：** {current_p_prep} 天")
            st.write(f"**配方產量：** 每次 {current_p_yield} 個/份")
            
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
                        idx = df_products.index[df_products['id'] == current_p_id].tolist()[0]
                        df_products.at[idx, 'name'] = new_name
                        df_products.at[idx, 'price'] = new_price
                        df_products.at[idx, 'prep_days'] = new_prep
                        df_products.at[idx, 'batch_yield'] = new_yield
                        
                        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Products", data=df_products)
                        st.cache_data.clear()
                        
                        st.session_state.selected_dessert = new_name
                        st.session_state[edit_prod_key] = False
                        st.toast("✅ 品項修改成功！")
                        st.rerun()
            
            st.write("") 
            
            del_confirm_key = f"del_confirm_{current_p_id}"
            if del_confirm_key not in st.session_state: st.session_state[del_confirm_key] = False
                
            if not st.session_state[del_confirm_key]:
                if st.button("🗑️ 刪除此甜點", key=f"btn_del_init_{current_p_id}", use_container_width=True):
                    st.session_state[del_confirm_key] = True
                    st.rerun()
            else:
                st.warning("⚠️ 是否確定刪除？（專屬配方也會同步移除且無法恢復喔！）")
                c_del1, c_del2 = st.columns(2)
                with c_del1:
                    if st.button("🚨 確定刪除", key=f"btn_del_confirm_{current_p_id}", use_container_width=True):
                        # 刪除產品及關聯的 BOM
                        df_products_clean = df_products[df_products['id'] != current_p_id]
                        df_bom_clean = df_bom[df_bom['product_id'] != current_p_id]
                        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Products", data=df_products_clean)
                        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Product_BOM", data=df_bom_clean)
                        st.cache_data.clear()
                        
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
            
            df_bom_filtered = df_bom[df_bom['product_id'] == current_p_id]
            df_bom_display = pd.merge(df_bom_filtered, df_ingredients, left_on='ingredient_id', right_on='id')
            
            if df_bom_display.empty: 
                st.caption("這款甜點目前沒有配方，請從下方新增喔。")
            else:
                for _, row in df_bom_display.iterrows():
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 1])
                        c1.write(f"🧈 **{row['name']}** ｜ ⚖️ {row['required_quantity']} {row['unit']}")
                        with c2:
                            edit_bom_key = f"edit_bom_active_{current_p_id}_{row['ingredient_id']}"
                            if edit_bom_key not in st.session_state: st.session_state[edit_bom_key] = False
                            
                            st.markdown("""
                                <style>
                                div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"] {
                                    flex-direction: row !important; flex-wrap: nowrap !important; gap: 6px !important;
                                }
                                div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"] {
                                    min-width: 0px !important;
                                }
                                </style>
                            """, unsafe_allow_html=True)
                            
                            c_edit_btn, c_del_btn = st.columns(2)
                            with c_edit_btn:
                                if not st.session_state[edit_bom_key]:
                                    if st.button("✏️", key=f"btn_bom_open_{row['ingredient_id']}", use_container_width=True):
                                        st.session_state[edit_bom_key] = True
                                        st.rerun()
                                else:
                                    if st.button("❌", key=f"btn_bom_close_{row['ingredient_id']}", use_container_width=True):
                                        st.session_state[edit_bom_key] = False
                                        st.rerun()
                            with c_del_btn:
                                if st.button("🗑️", key=f"bdel_{row['ingredient_id']}", use_container_width=True):
                                    df_bom_clean = df_bom[~((df_bom['product_id'] == current_p_id) & (df_bom['ingredient_id'] == row['ingredient_id']))]
                                    conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Product_BOM", data=df_bom_clean)
                                    st.cache_data.clear()
                                    st.toast("🗑️ 配方已刪除！")
                                    st.rerun()
                        
                        if st.session_state[edit_bom_key]:
                            with st.form(f"edit_bom_form_{row['ingredient_id']}"):
                                new_qty = st.number_input("新數量", value=float(row['required_quantity']), step=5.0)
                                if st.form_submit_button("儲存", use_container_width=True):
                                    mask = (df_bom['product_id'] == current_p_id) & (df_bom['ingredient_id'] == row['ingredient_id'])
                                    df_bom.loc[mask, 'required_quantity'] = new_qty
                                    conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Product_BOM", data=df_bom)
                                    st.cache_data.clear()
                                    
                                    st.session_state[edit_bom_key] = False
                                    st.toast("✅ 配方修改成功！")
                                    st.rerun()
                                
            if not df_ingredients.empty:
                with st.form("add_bom_form", clear_on_submit=True):
                    st.write(f"➕ **加入新原料 (製作 {current_p_yield} 個所需的量)**")
                    c_ing, c_qty, c_btn = st.columns([2, 2, 1])
                    ing_options = {f"{row['name']} ({row['unit']})": row['id'] for _, row in df_ingredients.iterrows()}
                    with c_ing: selected_ing = st.selectbox("選擇原料", list(ing_options.keys()), label_visibility="collapsed")
                    with c_qty: req_qty = st.number_input("數量", min_value=0.0, step=1.0, label_visibility="collapsed")
                    with c_btn:
                        if st.form_submit_button("加入", use_container_width=True):
                            i_id = int(ing_options[selected_ing])
                            # 檢查是否存在
                            mask = (df_bom['product_id'] == current_p_id) & (df_bom['ingredient_id'] == i_id)
                            if df_bom[mask].empty:
                                new_bom = pd.DataFrame([{"product_id": current_p_id, "ingredient_id": i_id, "required_quantity": req_qty}])
                                df_bom_updated = pd.concat([df_bom, new_bom], ignore_index=True)
                            else:
                                df_bom.loc[mask, 'required_quantity'] = req_qty
                                df_bom_updated = df_bom
                                
                            conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Product_BOM", data=df_bom_updated)
                            st.cache_data.clear()
                            st.toast("✅ 配方加入成功！")
                            st.rerun()

# ===== 頁面 4：成本分析 =====
if page == "成本分析":
    tab_ing_cost, tab_other_cost, tab_profit = st.tabs(["🛒 原物料單價設定", "📦 包材與雜支設定", "📊 利潤試算預覽"])
    
    with tab_ing_cost:
        st.markdown("### 🛒 原物料單價設定")
        st.markdown("請在這裡輸入各項原物料的**「每單位成本」**，或使用下方的快速換算工具。")
        
        with st.expander("🧮 記不住單價？使用「總量與總價」快速換算並儲存", expanded=True):
            if df_ingredients.empty:
                st.caption("目前沒有物料，請先到「庫存總覽」新增物料。")
            else:
                calc_options = {row['name']: row['id'] for _, row in df_ingredients.iterrows()}
                calc_units = {row['name']: row['unit'] for _, row in df_ingredients.iterrows()}
                
                col_sel, col_p, col_w = st.columns(3)
                with col_sel: selected_ing_name = st.selectbox("1. 選擇要設定的物料", list(calc_options.keys()), key="calc_ing_sel")
                with col_p: total_money = st.number_input("2. 購買總金額 ($)", min_value=0.0, step=1.0, value=0.0)
                with col_w:
                    current_unit = calc_units[selected_ing_name]
                    total_qty = st.number_input(f"3. 購買總量 ({current_unit})", min_value=0.0001, step=1.0, value=1.0)
                
                if total_money > 0 and total_qty > 0:
                    calculated_unit_price = total_money / total_qty
                    st.success(f"💡 換算結果：每 1 {current_unit} 的單價為 **$ {calculated_unit_price:.4f}**")
                    
                    if st.button(f"💾 直接更新「{selected_ing_name}」的每單位成本", use_container_width=True):
                        target_id = calc_options[selected_ing_name]
                        df_ingredients.loc[df_ingredients['id'] == target_id, 'unit_price'] = calculated_unit_price
                        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Ingredients", data=df_ingredients)
                        st.cache_data.clear()
                        st.toast(f"💰 已成功更新 {selected_ing_name} 單價為 $ {calculated_unit_price:.4f}！", icon="✅")
                        st.rerun()

        st.write("---")
        st.markdown("##### 📋 所有物料單價總覽 (亦可在下方表格直接修改)")
        
        if not df_ingredients.empty:
            df_ing_display = df_ingredients[['id', 'name', 'unit', 'unit_price']].copy()
            df_ing_display['unit_price'] = pd.to_numeric(df_ing_display['unit_price'], errors='coerce').fillna(0.0)
            
            with st.form("update_ing_price_form"):
                edited_df_ing = st.data_editor(
                    df_ing_display,
                    column_config={
                        "id": None,
                        "name": st.column_config.TextColumn("物料名稱", disabled=True),
                        "unit": st.column_config.TextColumn("單位", disabled=True),
                        "unit_price": st.column_config.NumberColumn("每單位成本 ($)", min_value=0.0, format="$ %.4f", step=0.0001)
                    },
                    use_container_width=True, hide_index=True
                )
                
                if st.form_submit_button("💾 儲存下方表格內所有手動修改", use_container_width=True):
                    for _, row in edited_df_ing.iterrows():
                        df_ingredients.loc[df_ingredients['id'] == row['id'], 'unit_price'] = row['unit_price']
                    conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Ingredients", data=df_ingredients)
                    st.cache_data.clear()
                    st.toast("✅ 物料單價已全面更新！", icon="💰")
                    st.rerun()

    with tab_other_cost:
        st.markdown("### 📦 附加成本與時間設定")
        
        if df_products.empty:
            st.warning("目前沒有甜點品項，請先到「配方設定」新增！")
        else:
            prod_names = df_products['name'].tolist()
            selected_prod_name = st.selectbox("🎯 請選擇要設定的甜點", prod_names)
            prod_row = df_products[df_products['name'] == selected_prod_name].iloc[0]
            
            with st.form(f"form_other_cost_{prod_row['id']}"):
                st.markdown(f"#### ✏️ 調整【{selected_prod_name}】的設定")
                
                c_wage, c_pack = st.columns(2)
                with c_wage:
                    val_hourly_wage = float(prod_row.get('hourly_wage', 200.0)) if pd.notna(prod_row.get('hourly_wage', 200.0)) else 200.0
                    new_hourly_wage = st.number_input("基本時薪 ($/時)", min_value=0.0, value=val_hourly_wage, step=5.0)
                with c_pack:
                    val_pack = float(prod_row.get('packaging_cost', 0.0)) if pd.notna(prod_row.get('packaging_cost', 0.0)) else 0.0
                    new_packaging_cost = st.number_input("單份包材費 ($/份)", min_value=0.0, value=val_pack, step=1.0)
                
                st.write("---")
                st.markdown("##### ⏱️ 製作時間與水電雜支設定 (核心對照組)")
                
                st.markdown("**➡️ 製作 1 份配方：**")
                c_h1, c_o1 = st.columns(2)
                with c_h1:
                    val_h1 = float(prod_row.get('production_hours', 0.0)) if pd.notna(prod_row.get('production_hours', 0.0)) else 0.0
                    new_h1 = st.number_input("製作時間 (1份) (小時)", min_value=0.0, value=val_h1, step=0.5)
                with c_o1:
                    val_o1 = float(prod_row.get('overhead_cost', 0.0)) if pd.notna(prod_row.get('overhead_cost', 0.0)) else 0.0
                    new_o1 = st.number_input("水電雜支 (1份) ($)", min_value=0.0, value=val_o1, step=5.0)
                
                st.markdown("**➡️ 製作 2 份配方 (可聯烤省時省電)：**")
                c_h2, c_o2 = st.columns(2)
                with c_h2:
                    val_h2 = float(prod_row.get('production_hours_2', 0.0)) if pd.notna(prod_row.get('production_hours_2', 0.0)) else 0.0
                    new_h2 = st.number_input("製作時間 (2份) (小時)", min_value=0.0, value=val_h2, step=0.5)
                with c_o2:
                    val_o2 = float(prod_row.get('overhead_cost_2', 0.0)) if pd.notna(prod_row.get('overhead_cost_2', 0.0)) else 0.0
                    new_o2 = st.number_input("水電雜支 (2份) ($)", min_value=0.0, value=val_o2, step=5.0)
                
                st.markdown("**➡️ 製作 3 份配方 (最大產能攤提)：**")
                c_h3, c_o3 = st.columns(2)
                with c_h3:
                    val_h3 = float(prod_row.get('production_hours_3', 0.0)) if pd.notna(prod_row.get('production_hours_3', 0.0)) else 0.0
                    new_h3 = st.number_input("製作時間 (3份) (小時)", min_value=0.0, value=val_h3, step=0.5)
                with c_o3:
                    val_o3 = float(prod_row.get('overhead_cost_3', 0.0)) if pd.notna(prod_row.get('overhead_cost_3', 0.0)) else 0.0
                    new_o3 = st.number_input("水電雜支 (3份) ($)", min_value=0.0, value=val_o3, step=5.0)
                
                # 自動辨識自訂欄位 (已把 target_margin 和 items_per_box 加入忽略清單)
                ignored_cols = [
                    'id', 'name', 'price', 'prep_days', 'batch_yield', 'labor_cost', 
                    'production_minutes', 'production_hours', 'production_hours_2', 
                    'production_hours_3', 'overhead_cost', 'overhead_cost_2', 
                    'overhead_cost_3', 'hourly_wage', 'packaging_cost',
                    'target_margin', 'items_per_box'  # 👈 關鍵修改：告訴系統忽略這兩個英文欄位
                ]
                custom_cols = [col for col in df_products.columns if col not in ignored_cols]
                
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
                
                if st.form_submit_button("💾 儲存此甜點的所有成本與時間設定", use_container_width=True):
                    idx = df_products.index[df_products['id'] == prod_row['id']].tolist()[0]
                    df_products.at[idx, 'hourly_wage'] = new_hourly_wage
                    df_products.at[idx, 'packaging_cost'] = new_packaging_cost
                    df_products.at[idx, 'production_hours'] = new_h1
                    df_products.at[idx, 'overhead_cost'] = new_o1
                    df_products.at[idx, 'production_hours_2'] = new_h2
                    df_products.at[idx, 'overhead_cost_2'] = new_o2
                    df_products.at[idx, 'production_hours_3'] = new_h3
                    df_products.at[idx, 'overhead_cost_3'] = new_o3
                    
                    for k, v in new_custom_values.items():
                        df_products.at[idx, k] = v
                        
                    conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Products", data=df_products)
                    st.cache_data.clear()
                    st.toast(f"✅ 【{selected_prod_name}】設定已成功儲存！", icon="💾")
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
                        if safe_name not in df_products.columns:
                            df_products[safe_name] = 0.0
                            conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Products", data=df_products)
                            st.cache_data.clear()
                            st.toast(f"✅ 已成功新增「{safe_name}」欄位！")
                            st.rerun()
                        else:
                            st.error("⚠️ 此項目可能已經存在！")

    with tab_profit:
        st.markdown("### 🎯 多份數定價與利潤精算機")
        
        if df_products.empty:
            st.warning("目前沒有甜點品項，請先到「配方設定」新增！")
        else:
            import math
            
            # --- 隱藏的底層資料計算 ---
            base_cols = ['id', 'name', 'price', 'prep_days', 'batch_yield', 'labor_cost', 'production_minutes', 'target_margin', 'items_per_box']
            batch_calc_cols = ['hourly_wage', 'production_hours', 'production_hours_2', 'production_hours_3', 'overhead_cost', 'overhead_cost_2', 'overhead_cost_3']
            per_unit_cost_cols = [col for col in df_products.columns if col not in base_cols + batch_calc_cols]
            
            m_pb = pd.merge(df_products, df_bom, left_on='id', right_on='product_id', how='left')
            df_i = df_ingredients[['id', 'name', 'unit_price', 'unit']].rename(columns={'id': 'ingredient_id', 'name': 'ing_name', 'unit': 'ing_unit'})
            df_raw = pd.merge(m_pb, df_i, on='ingredient_id', how='left')
            
            # 🚨 關鍵修正 1：將所有新欄位加入檢查清單，若為空白則自動補為 0
            all_numeric_cols = ['price', 'batch_yield', 'prep_days', 'target_margin', 'items_per_box'] + batch_calc_cols + per_unit_cost_cols
            for col in all_numeric_cols:
                if col in df_raw.columns:
                    df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce').fillna(0.0)
            
            # 確保產品名稱沒有空白
            if 'name' in df_raw.columns:
                df_raw['name'] = df_raw['name'].fillna("未命名")
            
            df_raw['ing_total_cost'] = df_raw['required_quantity'] * df_raw['unit_price']
            df_raw['ing_total_cost'] = df_raw['ing_total_cost'].fillna(0.0)
            
            group_keys = [col for col in df_products.columns if col not in ['labor_cost', 'production_minutes']]
            
            # 🚨 關鍵修正 2：加上 dropna=False，要求系統保留所有包含空白欄位的甜點
            df_product_ing = df_raw.groupby(group_keys, dropna=False)['ing_total_cost'].sum().reset_index()
            df_product_ing['單盒包材與附加總和'] = df_product_ing[per_unit_cost_cols].sum(axis=1)
            
            # --- 精算機顯示區塊 ---
            # 過濾掉可能為空的名字
            distinct_products = [n for n in df_product_ing['name'].unique() if pd.notna(n) and n != "未命名"]
            
            if distinct_products:
                c_sel, c_margin, c_box = st.columns([1.5, 1.5, 1])
                with c_sel: 
                    selected_prod = st.selectbox("🔍 1. 請選擇甜點品項", distinct_products, key="pricing_calc_prod")
                
                idx = df_products.index[df_products['name'] == selected_prod].tolist()[0]
                default_margin = float(df_products.at[idx, 'target_margin']) if 'target_margin' in df_products.columns and pd.notna(df_products.at[idx, 'target_margin']) else 60.0
                default_box = int(df_products.at[idx, 'items_per_box']) if 'items_per_box' in df_products.columns and pd.notna(df_products.at[idx, 'items_per_box']) else 1
                
                with c_margin: 
                    target_margin = st.slider("🎯 2. 設定目標毛利率 (%)", min_value=10, max_value=90, value=int(default_margin), step=5)
                with c_box: 
                    items_per_box = st.number_input("📦 3. 每盒入數", min_value=1, value=default_box, step=1)
                
                if st.button(f"💾 儲存【{selected_prod}】的毛利與包裝設定", use_container_width=True):
                    df_products.at[idx, 'target_margin'] = target_margin
                    df_products.at[idx, 'items_per_box'] = items_per_box
                    conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Products", data=df_products)
                    st.cache_data.clear()
                    st.toast(f"✅ {selected_prod} 的專屬設定已成功儲存！", icon="💾")
                    st.rerun()

                prod_data = df_product_ing[df_product_ing['name'] == selected_prod].iloc[0]
                base_yield = prod_data['batch_yield'] if prod_data['batch_yield'] > 0 else 1
                pricing_rows = []
                
                for batches in [1, 2, 3]:
                    total_items = int(base_yield * batches)
                    total_boxes = math.ceil(total_items / items_per_box)
                    
                    if batches == 1:
                        batch_hours = prod_data['production_hours']
                        batch_overhead = prod_data['overhead_cost']
                    elif batches == 2:
                        batch_hours = prod_data['production_hours_2'] if prod_data['production_hours_2'] > 0 else prod_data['production_hours'] * 2
                        batch_overhead = prod_data['overhead_cost_2'] if prod_data['overhead_cost_2'] > 0 else prod_data['overhead_cost'] * 2
                    elif batches == 3:
                        batch_hours = prod_data['production_hours_3'] if prod_data['production_hours_3'] > 0 else prod_data['production_hours'] * 3
                        batch_overhead = prod_data['overhead_cost_3'] if prod_data['overhead_cost_3'] > 0 else prod_data['overhead_cost'] * 3
                    
                    ing_cost = round(prod_data['ing_total_cost'] * batches, 1)
                    labor_cost = round(batch_hours * prod_data['hourly_wage'], 1)
                    extra_cost = round(batch_overhead + (prod_data['單盒包材與附加總和'] * total_boxes), 1)
                    total_cost = round(ing_cost + labor_cost + extra_cost, 1)
                    
                    suggested_total_revenue = round(total_cost / (1 - target_margin / 100), 0)
                    suggested_box_price = round(suggested_total_revenue / total_boxes, 0) if total_boxes > 0 else 0
                    total_profit = round(suggested_total_revenue - total_cost, 0)
                    
                    pricing_rows.append({
                        "製作規模": f"製作 {batches} 份配方",
                        "總產出 / 總盒數": f"{total_items} 個 ({total_boxes} 盒)",
                        "食材總成本": f"$ {ing_cost}",
                        "人事總成本": f"$ {labor_cost}",
                        "附加總成本": f"$ {extra_cost}",
                        "總成本 (A)": f"$ {total_cost}",
                        "應賣總金額 (B)": f"$ {int(suggested_total_revenue)}",
                        f"單盒建議售價 ({items_per_box}入)": f"$ {int(suggested_box_price)}",
                        "預估最後總利潤 (B-A)": f"$ {int(total_profit)}"
                    })
                
                df_pricing = pd.DataFrame(pricing_rows)
                st.write("")
                st.markdown(f"📊 **【 {selected_prod} 】定價對照表** (目標毛利：{target_margin}% | 包裝規格：{items_per_box} 入/盒)")
                st.dataframe(df_pricing, use_container_width=True, hide_index=True)