import flet as ft
import urllib.request
import json
import threading
import time
import datetime

# ==========================================
# 1. CONFIGURATION & THEME
# ==========================================
SERVER_URL = "https://restaurent-server-vzsj.onrender.com"
DATA_ENDPOINT = f"{SERVER_URL}/data"

# Theme Colors - Matches your "SmartOps" design
COLOR_BG = "#F5F7FA"           
COLOR_SURFACE = "#FFFFFF"      
COLOR_PRIMARY = "#2563EB"      
COLOR_SECONDARY = "#64748B"    
COLOR_SUCCESS = "#10B981"      
COLOR_WARNING = "#F59E0B"      
COLOR_DANGER = "#EF4444"       
COLOR_TEXT_MAIN = "#1E293B"    
COLOR_TEXT_MUTED = "#94A3B8"   

# Global State
app_state = {
    "running": True,
    "server_online": False,
}

# ==========================================
# 2. UTILS & NETWORK LAYER
# ==========================================
def get_hex_opacity(hex_color, opacity):
    try:
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 3:
            hex_color = ''.join([c*2 for c in hex_color])
        if len(hex_color) != 6:
            return "#000000"
        alpha = int(opacity * 255)
        if alpha < 0: alpha = 0
        if alpha > 255: alpha = 255
        return f"#{alpha:02x}{hex_color}"
    except Exception:
        return "#000000"

def http_get_json(url, timeout=4):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = resp.read()
                return json.loads(data.decode("utf-8"))
    except Exception:
        return None

def check_server_health():
    try:
        req = urllib.request.Request(DATA_ENDPOINT, method="HEAD")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False

# ==========================================
# 3. UI COMPONENTS
# ==========================================
Icons = ft.icons

def get_status_badge(is_online):
    color = COLOR_SUCCESS if is_online else COLOR_DANGER
    text = "SYSTEM ONLINE" if is_online else "SYSTEM OFFLINE"
    icon = Icons.WIFI if is_online else Icons.WIFI_OFF

    return ft.Container(
        content=ft.Row([
            ft.Icon(icon, size=16, color="white"),
            ft.Text(text, size=12, weight="bold", color="white")
        ], alignment="center", spacing=6),
        bgcolor=color,
        padding=ft.padding.symmetric(horizontal=12, vertical=6),
        border_radius=20,
        animate=ft.Animation(300, "easeInOut")
    )

def kpi_card(title, icon_name, value_ref, color):
    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Container(
                    content=ft.Icon(icon_name, size=24, color=color),
                    bgcolor=get_hex_opacity(color, 0.1),
                    padding=10,
                    border_radius=12
                ),
                ft.Text(title, size=14, color=COLOR_TEXT_MUTED, weight="w600")
            ], spacing=12, alignment="center"),
            ft.Container(height=4),
            ft.Text("...", ref=value_ref, size=28, weight="bold", color=COLOR_TEXT_MAIN)
        ]),
        bgcolor=COLOR_SURFACE,
        padding=20,
        border_radius=16,
        expand=True,
        shadow=ft.BoxShadow(blur_radius=15, color="#0A000000", offset=ft.Offset(0, 4)),
        animate=ft.Animation(400, "easeOut"),
    )

def detailed_table_row(t_id, status, avail, orders):
    s_bg = "#F3F4F6"
    s_col = COLOR_SECONDARY
    s_icon = Icons.CIRCLE

    if status == "Customer_Called":
        s_bg, s_col, s_icon = "#FEF2F2", COLOR_DANGER, Icons.NOTIFICATIONS_ACTIVE
    elif status == "Waiter_Responded":
        s_bg, s_col, s_icon = "#FFFBEB", COLOR_WARNING, Icons.ROOM_SERVICE
    elif status == "Idle":
        s_bg, s_col, s_icon = "#ECFDF5", COLOR_SUCCESS, Icons.CHECK_CIRCLE

    return ft.DataRow(cells=[
        ft.DataCell(ft.Text(f"T-{t_id}", weight="bold", color=COLOR_TEXT_MAIN, size=14)),
        ft.DataCell(ft.Container(
            content=ft.Row([
                ft.Icon(s_icon, size=14, color=s_col),
                ft.Text(status.replace("_", " "), size=12, color=s_col, weight="bold")
            ], spacing=6),
            bgcolor=s_bg,
            padding=ft.padding.symmetric(horizontal=10, vertical=4),
            border_radius=6
        )),
        ft.DataCell(ft.Text(str(avail), color=COLOR_TEXT_MAIN, size=13)),
        ft.DataCell(
            ft.Text(
                str(orders),
                weight="bold",
                size=13,
                color=COLOR_PRIMARY if str(orders).isdigit() and int(orders) > 0 else COLOR_TEXT_MUTED)
        ),
    ])

# ==========================================
# 4. MAIN APPLICATION
# ==========================================

def main(page: ft.Page):
    # --- Page Config ---
    page.title = "Restaurant SmartOps"
    page.bgcolor = COLOR_BG
    page.padding = 0
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(font_family="Roboto") 

    # --- UI References ---
    ref_total_calls = ft.Ref[ft.Text]()
    ref_active_needs = ft.Ref[ft.Text]()
    ref_avg_resp = ft.Ref[ft.Text]()
    ref_avg_dlv = ft.Ref[ft.Text]()
    ref_status_indicator = ft.Ref[ft.Container]()
    ref_time = ft.Ref[ft.Text]()

    # UI Ref for dashboard's table view
    ref_dashboard_table = ft.Ref[ft.DataTable]()

    # UI Ref for live dashboard floor grid
    ref_dashboard_live_grid = ft.Ref[ft.GridView]()

    current_menu_index = {"value": 0}

    # --- Header ---
    shared_header = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text("SmartOps", size=24, weight="900", color=COLOR_TEXT_MAIN),
                    ft.Text(ref=ref_time, value="Connecting...", size=13, color=COLOR_TEXT_MUTED, italic=True)
                ], spacing=2),
                ft.Container(ref=ref_status_indicator, content=get_status_badge(False))
            ], alignment="space_between", vertical_alignment="center"),
        ]),
        padding=ft.padding.only(left=24, right=24, top=40, bottom=16),
        bgcolor=COLOR_BG,
    )

    # --- Charts ---
    chart_data_points = [ft.LineChartDataPoint(i, 0) for i in range(7)]
    
    traffic_chart = ft.LineChart(
        data_series=[
            ft.LineChartData(
                data_points=chart_data_points,
                stroke_width=4,
                color=COLOR_PRIMARY,
                curved=True,
                stroke_cap_round=True,
                below_line_bgcolor=get_hex_opacity(COLOR_PRIMARY, 0.15),
            )
        ],
        border=ft.border.all(0),
        left_axis=ft.ChartAxis(labels_size=30, show_labels=True, labels_interval=20),
        bottom_axis=ft.ChartAxis(labels_size=24, show_labels=True, labels_interval=1),
        tooltip_bgcolor=COLOR_TEXT_MAIN,
        min_y=0,
        max_y=100,
        expand=True,
    )

    donut_sections = [
        ft.PieChartSection(50, title="Closed", color=COLOR_DANGER, radius=20, title_style=ft.TextStyle(size=12, color="white", weight="bold")),
        ft.PieChartSection(50, title="Open", color=COLOR_SUCCESS, radius=25, title_style=ft.TextStyle(size=12, color="white", weight="bold"))
    ]
    availability_chart = ft.PieChart(
        sections=donut_sections,
        sections_space=2,
        center_space_radius=40,
        expand=True,
    )

    # --- Views ---
    
    # Dashboard Table (For showing tables in the first page)
    dashboard_data_table = ft.DataTable(
        ref=ref_dashboard_table,
        columns=[
            ft.DataColumn(ft.Text("ID", weight="bold")),
            ft.DataColumn(ft.Text("STATUS", weight="bold")),
            ft.DataColumn(ft.Text("AVAIL", weight="bold")),
            ft.DataColumn(ft.Text("ORDERS", weight="bold")),
        ],
        rows=[],
        heading_row_color="#F1F5F9",
        data_row_min_height=45,
        column_spacing=25,
        divider_thickness=0.5,
    )

    # Dashboard floor status grid (new, shared with live grid in Monitor view)
    dashboard_live_grid = ft.GridView(
        ref=ref_dashboard_live_grid,
        expand=True,
        runs_count=2,
        max_extent=200,
        child_aspect_ratio=1.08, 
        spacing=12,
        run_spacing=12,
    )

    # 1. Dashboard View (now includes live floor status grid below other dashboard elements)
    view_dashboard = ft.Container(
        content=ft.Column([
            ft.Row([
                kpi_card("Total Calls", ft.icons.CALL, ref_total_calls, COLOR_PRIMARY),
                kpi_card("Active Needs", ft.icons.LOCAL_FIRE_DEPARTMENT, ref_active_needs, COLOR_DANGER)
            ], spacing=16),
            ft.Row([
                kpi_card("Avg Response", ft.icons.TIMER, ref_avg_resp, COLOR_WARNING),
                kpi_card("Avg Delivery", ft.icons.DELIVERY_DINING, ref_avg_dlv, COLOR_SUCCESS)
            ], spacing=16),
            
            ft.Container(height=20),
            
            ft.Text("Hourly Traffic", size=18, weight="bold", color=COLOR_TEXT_MAIN),
            ft.Container(
                content=traffic_chart,
                height=220,
                bgcolor=COLOR_SURFACE,
                border_radius=16,
                padding=20,
                shadow=ft.BoxShadow(blur_radius=15, color="#0A000000")
            ),
            
            ft.Container(height=20),

            ft.Text("Floor Availability", size=18, weight="bold", color=COLOR_TEXT_MAIN),
            ft.Container(
                content=ft.Row([
                    ft.Container(width=150, height=150, content=availability_chart),
                    ft.Column([
                        ft.Row([ft.Icon(ft.icons.CIRCLE, size=10, color=COLOR_SUCCESS), ft.Text("Available", size=13, color=COLOR_TEXT_MUTED)]),
                        ft.Container(height=5),
                        ft.Row([ft.Icon(ft.icons.CIRCLE, size=10, color=COLOR_DANGER), ft.Text("Occupied", size=13, color=COLOR_TEXT_MUTED)])
                    ], alignment="center")
                ], alignment="space_evenly"),
                height=180,
                bgcolor=COLOR_SURFACE,
                border_radius=16,
                padding=16,
                shadow=ft.BoxShadow(blur_radius=15, color="#0A000000")
            ),

            ft.Container(height=24),
            ft.Text("Live Floor Status", size=18, weight="bold", color=COLOR_TEXT_MAIN),
            ft.Container(
                content=dashboard_live_grid,
                bgcolor=COLOR_SURFACE,
                border_radius=16,
                padding=12,
                shadow=ft.BoxShadow(blur_radius=8, color="#07000000"),
                height=230,
                expand=False
            ),

            ft.Container(height=24),
            ft.Text("Live Table Status", size=18, weight="bold", color=COLOR_TEXT_MAIN),
            ft.Container(
                content=dashboard_data_table,
                bgcolor=COLOR_SURFACE,
                border_radius=16,
                padding=12,
                shadow=ft.BoxShadow(blur_radius=8, color="#07000000")
            ),
            ft.Container(height=32),
        ], spacing=12, scroll=ft.ScrollMode.ADAPTIVE),
        padding=ft.padding.symmetric(horizontal=24),
        expand=True,
    )

    # 2. Live Monitor View
    live_grid = ft.GridView(
        expand=True,
        runs_count=2,
        max_extent=220,
        child_aspect_ratio=1.1, 
        spacing=15,
        run_spacing=15,
    )
    view_monitor = ft.Container(
        content=ft.Column([
            ft.Text("Live Floor Status", size=20, weight="bold", color=COLOR_TEXT_MAIN),
            ft.Container(content=live_grid, expand=True)
        ]),
        padding=24,
        expand=True
    )

    # 3. Data Table View
    data_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("ID", weight="bold")),
            ft.DataColumn(ft.Text("STATUS", weight="bold")),
            ft.DataColumn(ft.Text("AVAIL", weight="bold")),
            ft.DataColumn(ft.Text("ORDERS", weight="bold")),
        ],
        rows=[],
        heading_row_color="#F1F5F9",
        data_row_min_height=45,
        column_spacing=25,
        divider_thickness=0.5,
    )
    view_list = ft.Container(
        content=ft.Column([
            ft.Text("Master Log", size=20, weight="bold", color=COLOR_TEXT_MAIN),
            ft.Container(
                content=ft.Row([data_table], scroll=ft.ScrollMode.ADAPTIVE),
                bgcolor=COLOR_SURFACE,
                border_radius=16,
                padding=10,
                expand=True,
                alignment=ft.alignment.top_left,
                shadow=ft.BoxShadow(blur_radius=10, color="#0A000000")
            )
        ]),
        padding=24,
        expand=True
    )

    # Content Area
    body_container = ft.Container(content=view_dashboard, expand=True)

    def switch_menu(idx):
        current_menu_index["value"] = idx
        if idx == 0:
            body_container.content = view_dashboard
        elif idx == 1:
            body_container.content = view_monitor
        elif idx == 2:
            body_container.content = view_list
        
        # This is the line that makes the magic happen:
        page.update()

    # --- Navigation Definition ---
    menu_items = [
        {"text": "Dashboard", "icon": Icons.DASHBOARD, "idx": 0},
        {"text": "Monitor", "icon": Icons.MONITOR_HEART, "idx": 1},
        {"text": "Data Logs", "icon": Icons.TABLE_CHART, "idx": 2},
    ]

    sidebar_menu = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=70,
        group_alignment=-0.95,
        bgcolor=COLOR_SURFACE,
        indicator_color=get_hex_opacity(COLOR_PRIMARY, 0.1),
        #selected_label_text_style=ft.TextStyle(color=COLOR_PRIMARY, weight="bold"),
        #unselected_label_text_style=ft.TextStyle(color=COLOR_TEXT_MUTED),
        destinations=[
            ft.NavigationRailDestination(
                icon=item["icon"],
                selected_icon=item["icon"],
                label=item["text"] 
            ) for item in menu_items
        ],
        on_change=lambda e: switch_menu(e.control.selected_index)
    )

    # Bottom Bar (Mobile)
    mobile_nav = ft.NavigationBar(
        selected_index=0,
        bgcolor=COLOR_SURFACE,
        indicator_color=get_hex_opacity(COLOR_PRIMARY, 0.1),
        destinations=[
            ft.NavigationDestination(icon=item["icon"], label=item["text"]) for item in menu_items
        ],
        on_change=lambda e: switch_menu(e.control.selected_index)
    )

    # --- Safe Responsive Layout ---
    def build_layout(width):
        page.controls.clear()
        
        # ADD THIS LINE: Ensure we are showing the correct content before building
        switch_menu(sidebar_menu.selected_index) 

        if width >= 660:
            page.add(
                ft.Row([
                    sidebar_menu,
                    ft.VerticalDivider(width=1, color="transparent"),
                    # Use body_container here so it shows the selected page
                    ft.Column([shared_header, body_container], expand=True, spacing=0) 
                ], expand=True, spacing=0)
            )
        else:
            page.add(
                ft.Column([
                    shared_header,
                    body_container,
                    mobile_nav
                ], expand=True, spacing=0)
            )
        page.update()

    page.on_resize = lambda e: build_layout(page.width)
    
    # Initial build safe check
    try:
        initial_w = page.width if page.width > 0 else 400
        build_layout(initial_w)
    except:
        build_layout(400) # Fallback

    # --- Background Threads ---
    def update_clock():
        while app_state["running"]:
            try:
                now_str = datetime.datetime.now().strftime("%a, %d %b • %I:%M %p")
                if getattr(ref_time, "current", None):
                    ref_time.current.value = now_str
                    ref_time.current.update()
                time.sleep(1)
            except: time.sleep(1)

    def _create_live_grid_controls(live_status, small=False):
        # Returns a list of containers for a live grid, small=False for main live, True for dashboard card (smaller)
        con_list = []
        for item in live_status:
            status = item.get('status', 'Idle')
            if status == "Customer_Called":
                bg, brd, icn = "#FEF2F2", COLOR_DANGER, ft.Icons.NOTIFICATIONS_ACTIVE
            elif status == "Waiter_Responded":
                bg, brd, icn = "#FFFBEB", COLOR_WARNING, ft.Icons.ROOM_SERVICE
            else:
                bg, brd, icn = COLOR_SURFACE, "transparent", ft.Icons.CHECK_CIRCLE
                if status != "Idle": brd = COLOR_SECONDARY
            con_list.append(
                ft.Container(
                    content=ft.Column([
                        ft.Row([ft.Text(f"T-{item.get('table_id')}", weight="bold", size=16 if small else 18), ft.Icon(icn, color=brd, size=16 if small else 20)], alignment="space_between"),
                        ft.Divider(height=5 if small else 10, color="transparent"),
                        ft.Text(status.replace("_", " "), color=COLOR_TEXT_MUTED, size=11 if small else 14, weight="bold"),
                        ft.Text(f"{item.get('minutes_ago', 0)} min ago", color=COLOR_TEXT_MUTED, size=10 if small else 12)
                    ]),
                    bgcolor=bg, border=ft.border.all(1, brd), border_radius=12, padding=10 if small else 16,
                    shadow=ft.BoxShadow(blur_radius=4 if small else 5, color="#05000000")
                )
            )
        return con_list

    def fetch_data():
        while app_state["running"]:
            try:
                is_online = check_server_health()
                app_state["server_online"] = is_online

                if getattr(ref_status_indicator, "current", None):
                    ref_status_indicator.current.content = get_status_badge(is_online)
                    ref_status_indicator.current.update()

                if is_online:
                    data = http_get_json(DATA_ENDPOINT)
                    if data and isinstance(data, dict):
                        # 1. Update Dashboard (KPI, charts, and now also table in the first page)
                        analytics = data.get('analytics', {})
                        if getattr(ref_total_calls, "current", None):
                            ref_total_calls.current.value = str(analytics.get('total', '-'))
                            ref_total_calls.current.update()
                        if getattr(ref_active_needs, "current", None):
                            ref_active_needs.current.value = str(analytics.get('open', '-'))
                            ref_active_needs.current.update()
                        if getattr(ref_avg_resp, "current", None):
                            ref_avg_resp.current.value = f"{analytics.get('avg_resp', '0')}m"
                            ref_avg_resp.current.update()
                        if getattr(ref_avg_dlv, "current", None):
                            ref_avg_dlv.current.value = f"{analytics.get('avg_dlv', '0')}m"
                            ref_avg_dlv.current.update()

                        # Chart Update
                        hourly = analytics.get('hourly', {})
                        points = [ft.LineChartDataPoint(i, float(hourly.get(str(i), 0))) for i in range(7)]
                        traffic_chart.data_series[0].data_points = points
                        traffic_chart.update()

                        # Pie Update
                        open_c = int(analytics.get('open_count', 0))
                        closed_c = int(analytics.get('closed_count', 0))
                        if open_c + closed_c == 0: open_c = 1 
                        availability_chart.sections[0].value = closed_c
                        availability_chart.sections[0].title = str(closed_c)
                        availability_chart.sections[1].value = open_c
                        availability_chart.sections[1].title = str(open_c)
                        availability_chart.update()

                        # Dashboard Table (now live_status table on dashboard too)
                        live_status = data.get('live_status', [])

                        if getattr(ref_dashboard_table, "current", None):
                            ref_dashboard_table.current.rows = [
                                detailed_table_row(i.get('table_id'), i.get('status'), "Yes", "0") for i in live_status
                            ]
                            ref_dashboard_table.current.update()

                        # --- NEW: Update dashboard live grid from live_status as well ---
                        if getattr(ref_dashboard_live_grid, "current", None):
                            ref_dashboard_live_grid.current.controls = _create_live_grid_controls(live_status, small=True)
                            ref_dashboard_live_grid.current.update()

                        # 2. Update Live Grid & Table for monitor and log views
                        if current_menu_index["value"] == 1:
                            live_grid.controls = _create_live_grid_controls(live_status, small=False)
                            live_grid.update()
                        
                        if current_menu_index["value"] == 2:
                            data_table.rows = [detailed_table_row(i.get('table_id'), i.get('status'), "Yes", "0") for i in live_status]
                            data_table.update()

            except Exception as e: 
                # print(f"Runtime error ignored in thread: {e}") 
                pass
            time.sleep(3)

    threading.Thread(target=update_clock, daemon=True).start()
    threading.Thread(target=fetch_data, daemon=True).start()

    def on_disconnect(e):
        app_state["running"] = False
    page.on_disconnect = on_disconnect
ft.app(target=main)