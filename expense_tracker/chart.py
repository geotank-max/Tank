
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import FuncFormatter
import pandas as pd
from .db import get_connection

BG = "#181533"
CARD = '#1d004c'
BORDER = '#252A3D'
TEXT = "#dddddc"
MUTED = '#6B7089'

CAT_COLORS = [
    '#7C6DF8',  # violet    — Food
    '#2DD4BF',  # teal      — Transport
    '#FFBC42',  # amber     — Shopping
    '#FF5470',  # coral     — Housing
    '#60A5FA',  # sky-blue  — Healthcare
    '#A78BFA',  # lavender  — Entertainment
    '#34D399',  # emerald   — Education
    '#F472B6',  # pink      — Other
]

BASE_DIR = Path(__file__).resolve().parent.parent
CHART_FOLDER = BASE_DIR / "static" / "charts"

def _currency(x, _pos):
    return f'${x:,.0f}'

def _style_axes(ax, grid_axis: str = 'y'):
    """Apply a consistent dark theme to an Axes object."""
    ax.set_facecolor(CARD)
    for spine in ax.spines.values():
        spine.set_color(BORDER)
    ax.tick_params(colors=MUTED, length=0)
    ax.set_axisbelow(True)
    kw = dict(color=BORDER, linewidth = 0.6, linestyle='--')
    if grid_axis in ('y', 'both'):
        ax.yaxis.grid(True, **kw)
    if grid_axis in ('x', 'both'):
        ax.xaxis.grid(True, **kw)


def generate_category_pie(df: pd.DataFrame, user_id: int) -> str | None:
    """Donut chart: expense share by category"""
    os.makedirs(CHART_FOLDER, exist_ok=True)

    if df.empty:
        return None
    
    df = df.copy()
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
    df['category_name'] = df['category_name'].fillna('Uncategorized')

    # 1. Clean and normalize category colors
    if 'category_color' in df.columns:
        df['category_color'] = df['category_color'].fillna('#6B7089')
        df['category_color'] = df['category_color'].astype(str).replace('nan', '#6B7089')
    else:
        df['category_color'] = '#6B7089'
    
    # 2. Compute category aggregates (Sorted high to low)
    cat_sum = df.groupby('category_name')['amount'].sum().sort_values(ascending=False)
    total = cat_sum.sum()

    # 3. FIX: Build a direct dictionary map from the DataFrame to prevent index mismatching
    unique_df = df.drop_duplicates(subset=['category_name'])
    color_map = dict(zip(unique_df['category_name'], unique_df['category_color']))
    
    # Extract colors in the exact matching sorted order of your cat_sum index slices
    colors = [color_map.get(cat, '#6B7089') for cat in cat_sum.index]
    colors = [c if isinstance(c, str) and c.startswith('#') else '#6B7089' for c in colors]

    # 4. Initialize Matplotlib Canvas Layout
    fig, ax = plt.subplots(figsize=(7, 6), facecolor=BG)
    ax.set_facecolor(BG)

    # 5. FIXED: Only call ax.pie ONCE and capture its return variables cleanly
    wedges, _, autotexts = ax.pie(
        cat_sum.values,
        labels=None,
        autopct=lambda p: f'{p:.1f}%' if p > 3 else '',
        colors=colors,
        startangle=90,
        pctdistance=0.78,
        wedgeprops=dict(linewidth=2.5, edgecolor=BG),
        textprops=dict(color=TEXT, fontsize=9, fontfamily='monospace'),
    ) 

    # Donut hole mask
    ax.add_patch(plt.Circle((0, 0), 0.56, fc=BG))

    # Center text strings
    ax.text(0, 0.12, f'${total:,.0f}',
            ha='center', va='center',
            fontsize=20, fontweight='bold', color=TEXT, fontfamily='monospace')
            
    ax.text(0, -0.12, 'TOTAL SPEND',
            ha='center', va='center',
            fontsize=7.5, color=MUTED, fontfamily='monospace')
    
    # Legend - Maps exactly to your colors array index mapping
    patches = [
        mpatches.Patch(color=colors[i], label=f'{cat} ${amt:,.2f}')
        for i, (cat, amt) in enumerate(cat_sum.items())
    ]
    
    ax.legend(handles=patches, loc='lower center',
              bbox_to_anchor=(0.5, -0.18), ncol=2,
              frameon=False, labelcolor=TEXT, fontsize=8.5,
              handlelength=1.2, handleheight=0.8)
    
    ax.set_title('Expense by Category', color=TEXT, fontsize=13,
                 fontweight='bold', pad=18)
    fig.subplots_adjust(bottom=0.2)

    # Save asset output
    filename = f"category_pie_{user_id}.png"
    fig.savefig(f"{CHART_FOLDER}/{filename}", bbox_inches='tight', facecolor=BG)
    plt.close(fig)
    return f"charts/{filename}"

def generate_monthly_bar(df: pd.DataFrame, user_id: int) -> str | None:
    os.makedirs(CHART_FOLDER, exist_ok=True)
    if df.empty:
        return None
    
    df = df.copy()
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
    
    # Force pandas to try multiple parsing formats to handle mixed date entries
    df["expense_date"] = pd.to_datetime(df['expense_date'], errors='coerce', format="mixed")
    
    # Drop records that couldn't be parsed into valid dates
    df = df.dropna(subset=['expense_date'])
    if df.empty:
        return None
        
    df['PERIOD'] = df['expense_date'].dt.to_period('M')

    # Aggregate by distinct chronological months
    monthly = df.groupby('PERIOD')['amount'].sum().sort_index()
    
    # Fallback safety: if you have a massive dataset, keep the last 12 separate months 
    # so the chart doesn't get overcrowded.
    monthly = monthly.tail(12) 
    
    labels = [p.strftime('%b %Y') for p in monthly.index]
    values = monthly.values

    fig, ax = plt.subplots(figsize=(8, 4.2), facecolor=BG)
    _style_axes(ax)
    
    x = range(len(values))
    
    # DYNAMIC COLORS: Creates a distinct color gradient across the months so they stand out
    cmap = plt.get_cmap('plasma') # Options: 'viridis', 'plasma', 'coolwarm', etc.
    bar_colors = [cmap(i / max(1, len(values) - 1)) for i in range(len(values))]
    
    bars = ax.bar(x, values, color=bar_colors, width=0.6,
                  edgecolor='#FFFFFF', linewidth=0.5, alpha=0.9)
    
    ax.set_xticks(x)
    ax.set_xticklabels(labels, color='#FFFFFF', fontsize=9, rotation=15) # Slight rotation helps readability
    ax.yaxis.set_major_formatter(FuncFormatter(_currency))
    ax.tick_params(axis='y', labelcolor='#FFFFFF', labelsize=9)

    # Value labels on top of each distinct month's bar
    ymax = max(values) if values.any() else 1
    for bar, val in zip(bars, values):
        if val > 0: # Only draw a value label if there is money spent
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + ymax * 0.025,
                    f'${val:,.0f}',
                    ha='center', va='bottom', fontsize=8.5,
                    color='#FFFFFF', fontfamily='monospace')
        
    ax.set_title('Monthly Spending Trend', color=TEXT, fontsize=13,
                 fontweight='bold', pad=14)
    fig.tight_layout()

    filename = f"monthly_bar_{user_id}.png"
    fig.savefig(f"{CHART_FOLDER}/{filename}", bbox_inches='tight', facecolor=BG)
    plt.close(fig)
    return f"charts/{filename}"


def generate_category_chart(df: pd.DataFrame, user_id: int) -> str | None:
    os.makedirs(CHART_FOLDER, exist_ok=True)

    if df.empty:
        return None
    
    df = df.copy()
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
    cat_sum = df.groupby('category_name')['amount'].sum().sort_values(ascending=False)
    colors = [CAT_COLORS [ i % len(CAT_COLORS)]
              for i in range(len(cat_sum))]

    fig, ax = plt.subplots(
        figsize=(8, max(3.0, len(cat_sum) * 0.65)), facecolor=BG
    )
    _style_axes(ax, grid_axis='x')

    y = range(len(cat_sum))
    bars = ax.barh(y, cat_sum.values, color=colors,
                   height=0.55, edgecolor=BG, linewidth=0.5)
    
    ax.set_yticks(y)
    ax.set_yticklabels(cat_sum.index, color=TEXT, fontsize=10)
    ax.xaxis.set_major_formatter(FuncFormatter(_currency))
    ax.tick_params(axis='x', labelcolor=MUTED, labelsize=9)

    xmax = cat_sum.max() if not cat_sum.empty else 1
    for bar, val in zip(bars, cat_sum.values):
        ax.text(bar.get_width() + xmax * 0.012,
                bar.get_y() + bar.get_height() / 2,
                f'${val:,.2f}',
                va='center', fontsize=8.5,
                color=TEXT, fontfamily='monospace')
        
    ax.set_xlim(right=xmax * 1.22)
    ax.set_title('Category Breakdown', color=TEXT, fontsize=13,
                 fontweight='bold', pad=14)
    fig.tight_layout()

    filename = f"category_chart_{user_id}.png"
    fig.savefig(f"{CHART_FOLDER}/{filename}",bbox_inches='tight', facecolor=BG) 
    plt.close(fig)
    return f"charts/{filename}"



def generate_monthly_chart():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            TO_CHAR(expense_date,'Mon YYYY'),
            SUM(amount)
        FROM expenses
        GROUP BY TO_CHAR(expense_date,'Mon YYYY'),
                 TO_CHAR(expense_date,'YYYYMM')
        ORDER BY TO_CHAR(expense_date,'YYYYMM')
    """)

    rows = cur.fetchall()

    months = [r[0] for r in rows]
    totals = [float(r[1]) for r in rows]

    plt.figure(figsize=(8,4))

    plt.bar(months, totals)

    plt.title("Monthly Spending Comparison")
    plt.xlabel("Month")
    plt.ylabel("Amount ($)")

    plt.tight_layout()

    os.makedirs(CHART_FOLDER, exist_ok=True)
    plt.savefig(CHART_FOLDER / "monthly_chart.png")
    plt.close()

    cur.close()
    conn.close()

    return True
    

    # Manager Dashboard cahrt

def generate_global_category_pie(df: pd.DataFrame) -> str | None:
    """Donut chart: Global manager view expense share by category"""
    if df.empty:
        return None
    
    df = df.copy()
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
    df['category_name'] = df['category_name'].fillna('Uncategorized')

    # 1. Clean and normalize category colors to eliminate NaN / Null leaks
    if 'category_color' in df.columns:
        df['category_color'] = df['category_color'].fillna('#6B7089')
        df['category_color'] = df['category_color'].astype(str).replace('nan', '#6B7089')
    else:
        df['category_color'] = '#6B7089'
    
    # 2. Compute category aggregates (Sorted high to low)
    cat_sum = df.groupby('category_name')['amount'].sum().sort_values(ascending=False)
    total = cat_sum.sum()

    # 3. Build a distinct dictionary map between category names and hex colors
    unique_df = df.drop_duplicates(subset=['category_name'])
    color_map = dict(zip(unique_df['category_name'], unique_df['category_color']))
    
    # Extract colors matching the sorted order of your chart slices perfectly
    colors = [color_map.get(cat, '#6B7089') for cat in cat_sum.index]
    colors = [c if isinstance(c, str) and c.startswith('#') else '#6B7089' for c in colors]

    # 4. Initialize Matplotlib Canvas Layout
    fig, ax = plt.subplots(figsize=(7, 6), facecolor=BG)
    ax.set_facecolor(BG)

    # 5. Render Pie Chart (Called ONCE safely)
    wedges, _, autotexts = ax.pie(
        cat_sum.values,
        labels=None,
        autopct=lambda p: f'{p:.1f}%' if p > 3 else '',
        colors=colors,  # Fully validated hex array with zero NaN leaks!
        startangle=90,
        pctdistance=0.78,
        wedgeprops=dict(linewidth=2.5, edgecolor=BG),
        textprops=dict(color=TEXT, fontsize=9, fontfamily='monospace'),
    ) 

    # Donut hole mask
    ax.add_patch(plt.Circle((0, 0), 0.56, fc=BG))

    # Center text strings
    ax.text(0, 0.12, f'${total:,.0f}',
            ha='center', va='center',
            fontsize=20, fontweight='bold', color=TEXT, fontfamily='monospace')
            
    ax.text(0, -0.12, 'TOTAL GLOBAL SPEND',
            ha='center', va='center',
            fontsize=7.5, color=MUTED, fontfamily='monospace')
    
    # Legend setup
    patches = [
        mpatches.Patch(color=colors[i], label=f'{cat} ${amt:,.2f}')
        for i, (cat, amt) in enumerate(cat_sum.items())
    ]
    
    ax.legend(handles=patches, loc='lower center',
              bbox_to_anchor=(0.5, -0.18), ncol=2,
              frameon=False, labelcolor=TEXT, fontsize=8.5,
              handlelength=1.2, handleheight=0.8)
    
    ax.set_title('Global Expense by Category', color=TEXT, fontsize=13,
                 fontweight='bold', pad=18)
    fig.subplots_adjust(bottom=0.2)

    # Save output asset asset string
    filename = "global_category_pie.png"
    fig.savefig(f"{CHART_FOLDER}/{filename}", bbox_inches='tight', facecolor=BG)
    plt.close(fig)
    return f"charts/{filename}"


def generate_global_monthly_line(df: pd.DataFrame) -> str | None:
    """Line Chart: Shows historical spending trend aggregated monthly across all accounts."""
    os.makedirs(CHART_FOLDER, exist_ok=True)
    if df.empty:
        return None
    
    df = df.copy()
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
    df["expense_date"] = pd.to_datetime(df['expense_date'], errors='coerce')
    df['PERIOD'] = df['expense_date'].dt.to_period('M')

    monthly = df.groupby('PERIOD')['amount'].sum().sort_index().tail(12) # last 12 months
    
    labels = [p.strftime('%b %Y') for p in monthly.index]
    values = monthly.values

    fig, ax = plt.subplots(figsize=(8, 4.2), facecolor=BG)
    _style_axes(ax, grid_axis='both')
    
    # Render line plot trend path
    ax.plot(labels, values, color='#2DD4BF', marker='o', linewidth=2.5, markersize=6, label="Total Spend")
    ax.fill_between(labels, values, color='#2DD4BF', alpha=0.1) # Soft shadow under line
    
    ax.yaxis.set_major_formatter(FuncFormatter(_currency))
    ax.tick_params(colors=TEXT, labelsize=9)
    
    for i, val in enumerate(values):
        ax.text(i, val + (max(values) * 0.03), f'${val:,.0f}', ha='center', fontsize=8, color=TEXT, fontfamily='monospace')

    ax.set_title('Global Monthly Spending Trend', color=TEXT, fontsize=13, fontweight='bold', pad=14)
    fig.tight_layout()

    filename = "global_monthly_line.png"
    fig.savefig(f"{CHART_FOLDER}/{filename}", bbox_inches='tight', facecolor=BG)
    plt.close(fig)
    return f"charts/{filename}"


def generate_global_user_bar(df: pd.DataFrame) -> str | None:
    """Horizontal Bar Chart: Ranks users from highest total spender down to lowest."""
    os.makedirs(CHART_FOLDER, exist_ok=True)
    if df.empty:
        return None
    
    df = df.copy()
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
    
    # Group sum metrics by unique username
    user_sum = df.groupby('username')['amount'].sum().sort_values(ascending=True) # Ascending looks better on horizontal bars

    fig, ax = plt.subplots(figsize=(8, max(3.5, len(user_sum) * 0.55)), facecolor=BG)
    _style_axes(ax, grid_axis='x')

    y = range(len(user_sum))
    bars = ax.barh(y, user_sum.values, color='#7C6DF8', height=0.6, edgecolor='#9381FF', linewidth=0.5)
    
    ax.set_yticks(y)
    ax.set_yticklabels(user_sum.index, color=TEXT, fontsize=10, fontweight='bold')
    ax.xaxis.set_major_formatter(FuncFormatter(_currency))
    ax.tick_params(axis='x', labelcolor=MUTED, labelsize=9)

    xmax = user_sum.max() if not user_sum.empty else 1
    for bar, val in zip(bars, user_sum.values):
        ax.text(bar.get_width() + xmax * 0.015, bar.get_y() + bar.get_height() / 2,
                f'${val:,.2f}', va='center', fontsize=8.5, color=TEXT, fontfamily='monospace')
        
    ax.set_xlim(right=xmax * 1.25)
    ax.set_title('Leaderboard: Total Spending by User', color=TEXT, fontsize=13, fontweight='bold', pad=14)
    fig.tight_layout()

    filename = "global_user_chart.png"
    fig.savefig(f"{CHART_FOLDER}/{filename}", bbox_inches='tight', facecolor=BG) 
    plt.close(fig)
    return f"charts/{filename}"
