import streamlit as st
from googleapiclient.discovery import build
from datetime import datetime
import pandas as pd
import io
from openpyxl import Workbook

# ✔️ 비밀번호 보호
PASSWORD = "isawesome^1"
input_pass = st.text_input("🔐 접속 비밀번호를 입력하세요", type="password")
if input_pass != PASSWORD:
    st.warning("올바른 비밀번호를 입력하세요.")
    st.stop()

# ✔️ YouTube API 연결
def get_youtube_service(api_key):
    return build("youtube", "v3", developerKey=api_key)

# ✔️ 채널 이름 가져오기
def get_channel_title(youtube, channel_id):
    response = youtube.channels().list(
        part="snippet",
        id=channel_id
    ).execute()
    return response['items'][0]['snippet']['title']

# ✔️ 업로드 영상 목록 가져오기
def get_uploads_playlist_id(youtube, channel_id):
    response = youtube.channels().list(
        part="contentDetails",
        id=channel_id
    ).execute()
    return response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

def get_videos(youtube, playlist_id):
    videos = []
    next_page_token = None
    while True:
        response = youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page_token
        ).execute()
        for item in response['items']:
            snippet = item['snippet']
            videos.append({
                "video_id": snippet['resourceId']['videoId'],
                "title": snippet['title'],
                "published_at": snippet['publishedAt'],
                "thumbnail": snippet['thumbnails']['medium']['url'],
                "video_url": f"https://www.youtube.com/watch?v={snippet['resourceId']['videoId']}"
            })
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break
    return videos

# ✔️ 조회수 가져오기
def get_video_views(youtube, video_ids):
    stats = []
    for i in range(0, len(video_ids), 50):
        response = youtube.videos().list(
            part="statistics",
            id=','.join(video_ids[i:i+50])
        ).execute()
        for item in response['items']:
            stats.append({
                "video_id": item['id'],
                "viewCount": int(item['statistics'].get('viewCount', 0))
            })
    return stats

# ✔️ UI 시작
st.set_page_config(layout="wide")
st.markdown("""
    <h2 style='text-align: left; color: #1E90FF;'>
        📊 YouTube 데이터 조회 Ver.1
    </h2>
""", unsafe_allow_html=True)

api_key = st.text_input("🔑 YouTube API 키", type="password")
channel_ids_raw = st.text_area("💼 채널 ID 여러 개 입력 (한 줄에 한 개씩 입력)")
channel_ids = [cid.strip() for cid in channel_ids_raw.split('\n') if cid.strip()]

start_date = st.date_input("📅 시작 날짜", datetime(2024, 1, 1))
end_date = st.date_input("📅 종료 날짜", datetime.today())

all_downloads = {}  # 🔄 통합 다운로드용 딕셔너리 초기화

if st.button("결과 조회") and api_key and channel_ids:
    youtube = get_youtube_service(api_key)
    tabs = st.tabs([f"📺 {get_channel_title(youtube, cid)}" for cid in channel_ids])

    for tab, channel_id in zip(tabs, channel_ids):
        with tab:
            try:
                channel_title = get_channel_title(youtube, channel_id)
                playlist_id = get_uploads_playlist_id(youtube, channel_id)
                videos = get_videos(youtube, playlist_id)

                df = pd.DataFrame(videos)
                df['published_at'] = pd.to_datetime(df['published_at']).dt.tz_localize(None)
                df = df[(df['published_at'] >= pd.to_datetime(start_date)) & (df['published_at'] <= pd.to_datetime(end_date))]

                if df.empty:
                    st.warning("선택한 기간에 업로드된 영상이 없습니다.")
                    continue

                video_ids = df['video_id'].tolist()
                views_data = get_video_views(youtube, video_ids)
                views_df = pd.DataFrame(views_data)
                df = df.merge(views_df, on='video_id')
                df['viewCount'] = df['viewCount'].astype(int)
                df = df.sort_values('published_at', ascending=False)

                total_views = df['viewCount'].sum()
                avg_views = df['viewCount'].mean()
                upload_count = len(df)

                st.markdown(f"**✅ 업로드 수:** {upload_count}개")
                st.markdown(f"**👁️ 총 조회수:** {total_views:,}회")
                st.markdown(f"**📊 평균 조회수:** {int(avg_views):,}회")

                # 월별 집계
                df['월'] = df['published_at'].dt.to_period('M').astype(str)
                monthly = df.groupby('월').agg({
                    'video_id': 'count',
                    'viewCount': ['sum', 'mean']
                })
                monthly.columns = ['업로드 수', '총 조회수', '평균 조회수']
                monthly = monthly.round(0).astype(int)

                monthly_display = monthly.copy()
                monthly_display['업로드 수'] = monthly_display['업로드 수'].map('{:,}'.format)
                monthly_display['총 조회수'] = monthly_display['총 조회수'].map('{:,}'.format)
                monthly_display['평균 조회수'] = monthly_display['평균 조회수'].map('{:,}'.format)

                st.markdown("#### 📅 월별 요약 통계")
                st.dataframe(monthly_display)

                st.markdown("#### 📈 월별 업로드 수")
                st.bar_chart(monthly[['업로드 수']])

                st.markdown("#### 👁️ 월별 총 조회수")
                st.bar_chart(monthly[['총 조회수']])

                # 🔥 조회수 TOP5
                st.markdown("#### 🏆 조회수 TOP 5")
                top5 = df.sort_values(by='viewCount', ascending=False).head(5)
                for i, row in enumerate(top5.itertuples(), 1):
                    st.markdown(f"""
                        <div style='display:flex; align-items:flex-start; margin-bottom:12px; background-color:#fdfdfd; padding:8px; border-radius:6px;'>
                            <img src="{row.thumbnail}" style="width:100px; border-radius:4px; margin-right:12px;">
                            <div style="max-width: 75%;">
                                <a href="{row.video_url}" target="_blank" style="text-decoration:none;">
                                    <h5 style="margin:0; color:#333;">[{i}] {row.title}</h5>
                                </a>
                                <p style="margin:4px 0 0; color:#666;">📅 {row.published_at.date()} | 👁️ {row.viewCount:,}회</p>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                st.markdown("#### 🚀 일자 별 영상")
                for _, row in df.iterrows():
                    st.markdown(f"""
                        <div style='display:flex; align-items:flex-start; margin-bottom:16px; background-color:#fafafa; padding:10px; border-radius:8px;'>
                            <img src="{row['thumbnail']}" style="width:120px; border-radius:4px; margin-right:16px;">
                            <div style="max-width: 75%;">
                                <a href="{row['video_url']}" target="_blank" style="text-decoration:none;">
                                    <h5 style="margin:0; color:#333;">{row['title']}</h5>
                                </a>
                                <p style="margin:4px 0 0; color:#666;">📅 {row['published_at'].date()} | 👁️ {row['viewCount']:,}회</p>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                download_df = df[['title', 'published_at', 'viewCount', 'video_url']]
                download_df.columns = ['영상 제목', '업로드일', '조회수', '영상 링크']
                towrite = io.BytesIO()
                download_df.to_excel(towrite, index=False, engine='openpyxl')
                st.download_button(f"📥 엑셀 다운로드 ({channel_title})", data=towrite.getvalue(), file_name=f"{channel_title}_분석결과.xlsx")

                all_downloads[channel_title] = download_df.copy()  # 🔄 통합 다운로드용 저장

            except Exception as e:
                st.error(f"❌ 오류 발생: {e}")

    # 🔽 통합 다운로드 버튼
    if all_downloads:
        st.markdown("---")
        st.markdown("### 📂 모든 채널 통합 엑셀 다운로드")
        combined_io = io.BytesIO()
        with pd.ExcelWriter(combined_io, engine='openpyxl') as writer:
            for sheet_name, df_sheet in all_downloads.items():
                df_sheet.to_excel(writer, sheet_name=sheet_name[:31], index=False)
        st.download_button("📥 통합 다운로드 (모든 채널)", data=combined_io.getvalue(), file_name="통합_유튜브_분석결과.xlsx")
