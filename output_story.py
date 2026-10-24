from upload_video import authenticate_youtube, upload_video

# Authenticate YouTube
youtube_client = authenticate_youtube()

# Upload the freshly rendered video
upload_video(
    youtube=youtube_client,
    file_path="output_story.mp4",
    title="ईदगाह - मुंशी प्रेमचंद | Hindi Classic Stories",
    description="NCERT Hindi Literature Class: Premchand's timeless story Idgah.",
    tags=["Idgah", "Premchand", "NCERT Stories", "Hindi Kahaniya"],
    privacy_status="private"
)