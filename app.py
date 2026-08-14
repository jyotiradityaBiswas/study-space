import os
import re
import uuid
from functools import wraps
from PIL import Image
from datetime import timedelta

import cloudinary
import cloudinary.uploader

from dotenv import load_dotenv

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_from_directory
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from werkzeug.utils import secure_filename

from database.database import (
    get_connection,
    initialize_database
)

from services.drive import (
    get_drive_service,
    get_cached_structure,
    get_children,
    get_folder,
    upload_file
)

from services.content_filter import validate_content

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]

app.config.update(
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="Lax"
)

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True
)

PENDING_UPLOAD_FOLDER = os.path.join(
    app.root_path,
    "pending_uploads"
)

os.makedirs(
    PENDING_UPLOAD_FOLDER,
    exist_ok=True
)

MAX_DOUBTS_PER_DAY = 4
MAX_REPLIES_PER_HOUR = 5

ALLOWED_IMAGE_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}

PROFILE_UPLOAD_FOLDER = os.path.join(
    app.root_path,
    "static",
    "uploads",
    "profile_pictures"
)

os.makedirs(
    PROFILE_UPLOAD_FOLDER,
    exist_ok=True
)

initialize_database()

@app.context_processor
def inject_notifications():

    if "user_id" not in session:
        return {
            "notifications": [],
            "unread_notifications": 0
        }

    connection = get_connection()

    notifications = connection.execute(
        """
        SELECT
            id,
            title,
            message,
            is_read,
            created_at
        FROM notifications
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 5
        """,
        (session["user_id"],)
    ).fetchall()

    unread_notifications = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM notifications
        WHERE user_id = %s
        AND is_read = FALSE
        """,
        (session["user_id"],)
    ).fetchone()["count"]

    connection.close()

    return {
        "notifications": notifications,
        "unread_notifications": unread_notifications
    }

def allowed_image(filename):
    return (
        "." in filename
        and filename.rsplit(
            ".",
            1
        )[1].lower() in ALLOWED_IMAGE_EXTENSIONS
    )


def login_required(route_function):
    @wraps(route_function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(
                url_for("login")
            )

        return route_function(
            *args,
            **kwargs
        )

    return wrapper

def admin_required(route_function):

    @wraps(route_function)
    def wrapper(*args, **kwargs):

        if not session.get("is_admin"):
            return redirect(
                url_for("admin")
            )

        return route_function(
            *args,
            **kwargs
        )

    return wrapper

@app.route("/")
@login_required
def index():
    service = get_drive_service()

    subjects = get_cached_structure(
        service
    )

    return render_template(
        "index.html",
        subjects=subjects
    )


@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if "user_id" in session:
        return redirect(
            url_for("index")
        )

    if request.method == "POST":

        display_name = request.form.get(
            "display_name",
            ""
        ).strip()

        username = request.form.get(
            "username",
            ""
        )

        password = request.form.get(
            "password",
            ""
        )

        if (
            not display_name
            or not username
            or not password
        ):
            return render_template(
                "register.html",
                error="Please fill in all fields."
            )

        if username != username.strip():
            return render_template(
                "register.html",
                error="Username cannot start or end with spaces."
            )

        username = username.lower()

        if not 3 <= len(username) <= 30:
            return render_template(
                "register.html",
                error=(
                    "Username must be between "
                    "3 and 30 characters."
                )
            )

        if not re.fullmatch(
            r"[a-z][a-z0-9_]*[a-z0-9]",
            username
        ):
            return render_template(
                "register.html",
                error=(
                    "Username must start with a letter "
                    "and contain only lowercase letters, "
                    "numbers, and underscores."
                )
            )

        if len(password) < 8:
            return render_template(
                "register.html",
                error="Password must be at least 8 characters."
            )

        connection = get_connection()

        existing_user = connection.execute(
            """
            SELECT id
            FROM users
            WHERE username = %s
            """,
            (username,)
        ).fetchone()

        if existing_user:
            connection.close()

            return render_template(
                "register.html",
                error="That username is already taken."
            )

        user_id = str(
            uuid.uuid4()
        )

        password_hash = generate_password_hash(
            password
        )

        connection.execute(
            """
            INSERT INTO users (
                id,
                username,
                display_name,
                password_hash
            )
            VALUES (%s, %s, %s, %s)
            """,
            (
                user_id,
                username,
                display_name,
                password_hash
            )
        )

        connection.commit()
        connection.close()

        session["user_id"] = user_id

        return redirect(
            url_for("index")
        )

    return render_template(
        "register.html",
        error=None
    )


@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if "user_id" in session:
        return redirect(
            url_for("index")
        )

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        connection = get_connection()

        user = connection.execute(
            """
            SELECT *
            FROM users
            WHERE username = %s
            """,
            (username,)
        ).fetchone()

        connection.close()

        if (
            not user
            or not check_password_hash(
                user["password_hash"],
                password
            )
        ):
            return render_template(
                "login.html",
                error="Invalid username or password."
            )

        session["user_id"] = user["id"]

        return redirect(
            url_for("index")
        )

    return render_template(
        "login.html",
        error=None
    )


@app.route("/logout")
def logout():
    session.clear()

    return redirect(
        url_for("login")
    )


@app.route(
    "/profile",
    methods=["GET", "POST"]
)
@login_required
def profile():

    user_id = session["user_id"]

    connection = get_connection()

    user = connection.execute(
        """
        SELECT
            id,
            username,
            display_name,
            profile_picture
        FROM users
        WHERE id = %s
        """,
        (user_id,)
    ).fetchone()

    points = connection.execute(
        """
        SELECT
            COALESCE(
                SUM(points),
                0
            ) AS total
        FROM contributions
        WHERE user_id = %s
        """,
        (user_id,)
    ).fetchone()["total"]

    connection.close()

    if not user:
        session.clear()

        return redirect(
            url_for("login")
        )

    return render_template(
        "profile.html",
        user=user,
        points=points,
        delete_error=request.args.get("delete_error")
    )


@app.route(
    "/profile/update",
    methods=["POST"]
)
@login_required
def update_profile():

    display_name = request.form.get(
        "display_name",
        ""
    ).strip()

    if not display_name:
        return redirect(
            url_for("profile")
        )

    if len(display_name) > 40:
        return redirect(
            url_for("profile")
        )

    connection = get_connection()

    connection.execute(
        """
        UPDATE users
        SET display_name = %s
        WHERE id = %s
        """,
        (
            display_name,
            session["user_id"]
        )
    )

    connection.commit()
    connection.close()

    return redirect(
        url_for("profile")
    )


@app.route(
    "/profile/picture",
    methods=["POST"]
)
@login_required
def upload_profile_picture():

    if "profile_picture" not in request.files:
        return redirect(url_for("profile"))

    file = request.files["profile_picture"]

    if not file.filename:
        return redirect(url_for("profile"))

    try:
        image = Image.open(file)
        image.verify()

        file.stream.seek(0)

        image = Image.open(file)
        image = image.convert("RGB")

    except Exception:
        return redirect(url_for("profile"))

    image.thumbnail(
        (512, 512),
        Image.Resampling.LANCZOS
    )

    connection = get_connection()

    user = connection.execute(
        """
        SELECT profile_picture
        FROM users
        WHERE id = %s
        """,
        (session["user_id"],)
    ).fetchone()

    try:

        upload_result = cloudinary.uploader.upload(
            file,
            folder="studyspace/profile_pictures",
            public_id=str(session["user_id"]),
            overwrite=True,
            resource_type="image"
        )

    except Exception:
        connection.close()
        return redirect(url_for("profile"))

    connection.execute(
        """
        UPDATE users
        SET profile_picture = %s
        WHERE id = %s
        """,
        (
            upload_result["secure_url"],
            session["user_id"]
        )
    )

    connection.commit()
    connection.close()

    return redirect(url_for("profile"))
    
@app.route("/profile/delete", methods=["POST"])
@login_required
def delete_account():
    user_id = session["user_id"]

    password = request.form.get(
        "password",
        ""
    )

    connection = get_connection()

    user = connection.execute(
        """
        SELECT password_hash
        FROM users
        WHERE id = %s
        """,
        (user_id,)
    ).fetchone()

    if not user:
        connection.close()
        session.clear()
        return redirect(url_for("login"))

    if not check_password_hash(
        user["password_hash"],
        password
    ):
        connection.close()

        return redirect(
            url_for("profile", delete_error="invalid_password")
        )

    connection.execute(
        """
        DELETE FROM contributions
        WHERE user_id = %s
        """,
        (user_id,)
    )

    connection.execute(
        """
        DELETE FROM users
        WHERE id = %s
        """,
        (user_id,)
    )

    connection.commit()
    connection.close()

    session.clear()

    return redirect(url_for("register"))


@app.route("/doubts")
@login_required
def doubts():

    connection = get_connection()

    doubts = connection.execute(
        """
        SELECT
            doubts.id,
            doubts.title,
            doubts.body,
            doubts.subject,
            doubts.chapter,
            doubts.created_at,
            users.display_name,
            users.profile_picture,
            COUNT(replies.id) AS reply_count
        FROM doubts
        JOIN users
            ON doubts.user_id = users.id
        LEFT JOIN replies
            ON doubts.id = replies.doubt_id
        GROUP BY
            doubts.id,
            doubts.title,
            doubts.body,
            doubts.subject,
            doubts.chapter,
            doubts.created_at,
            users.display_name,
            users.profile_picture
        ORDER BY doubts.created_at DESC
        """
    ).fetchall()

    connection.close()

    return render_template(
        "doubts.html",
        doubts=doubts
    )

@app.route(
    "/doubts/new",
    methods=["GET", "POST"]
)
@login_required
def create_doubt():

    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        body = request.form.get(
            "body",
            ""
        ).strip()

        valid, error = validate_content(title)

        if not valid:
            return render_template(
                "create_doubt.html",
                error=error
            )

        valid, error = validate_content(body)

        if not valid:
            return render_template(
                "create_doubt.html",
                error=error
            )

        subject = request.form.get(
            "subject",
            ""
        ).strip()

        chapter = request.form.get(
            "chapter",
            ""
        ).strip()

        valid, error = validate_content(subject)
        
        if not valid:
            return render_template(
                "create_doubt.html",
                error=error
            )
        
        valid, error = validate_content(chapter)
        
        if not valid:
            return render_template(
                "create_doubt.html",
                error=error
            )

        if not title or not body:
            return render_template(
                "create_doubt.html",
                error=(
                    "Please fill in the title "
                    "and question."
                )
            )

        connection = get_connection()

        doubt_count = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM doubts
            WHERE user_id = %s
            AND created_at >= NOW() - INTERVAL '24 hours'
            """,
            (session["user_id"],)
        ).fetchone()["count"]

        if doubt_count >= MAX_DOUBTS_PER_DAY:
            connection.close()

            return render_template(
                "create_doubt.html",
                error=(
                    "You can post a maximum of "
                    f"{MAX_DOUBTS_PER_DAY} doubts every 24 hours."
                )
            )

        cursor = connection.execute(
            """
            INSERT INTO doubts (
                user_id,
                title,
                body,
                subject,
                chapter
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                session["user_id"],
                title,
                body,
                subject or None,
                chapter or None
            )
        )

        doubt_id = cursor.fetchone()["id"]

        connection.execute(
            """
            INSERT INTO contributions (
                user_id,
                type,
                points
            )
            VALUES (%s, %s, %s)
            """,
            (
                session["user_id"],
                "doubt_opened",
                1
            )
        )

        connection.commit()
        connection.close()

        return redirect(
            url_for(
                "view_doubt",
                doubt_id=doubt_id
            )
        )

    return render_template(
        "create_doubt.html",
        error=None
    )


@app.route(
    "/doubts/<int:doubt_id>"
)
@login_required
def view_doubt(doubt_id):

    connection = get_connection()

    doubt = connection.execute(
        """
        SELECT
            doubts.*,
            users.display_name,
            users.profile_picture
        FROM doubts
        JOIN users
            ON doubts.user_id = users.id
        WHERE doubts.id = %s
        """,
        (doubt_id,)
    ).fetchone()

    if not doubt:
        connection.close()

        return "Doubt not found", 404

    replies = connection.execute(
        """
        SELECT
            replies.*,
            users.display_name,
            users.profile_picture
        FROM replies
        JOIN users
            ON replies.user_id = users.id
        WHERE replies.doubt_id = %s
        ORDER BY replies.created_at ASC
        """,
        (doubt_id,)
    ).fetchall()

    connection.close()

    return render_template(
        "doubt.html",
        doubt=doubt,
        replies=replies
    )

@app.route(
    "/doubts/<int:doubt_id>/edit",
    methods=["POST"]
)
@login_required
def edit_doubt(doubt_id):

    title = request.form.get(
        "title",
        ""
    ).strip()

    body = request.form.get(
        "body",
        ""
    ).strip()

    subject = request.form.get(
        "subject",
        ""
    ).strip()

    chapter = request.form.get(
        "chapter",
        ""
    ).strip()

    if not title or not body:
        return redirect(
            url_for(
                "view_doubt",
                doubt_id=doubt_id
            )
        )

    if len(title) > 200 or len(body) > 3000:
        return redirect(
            url_for(
                "view_doubt",
                doubt_id=doubt_id
            )
        )

    connection = get_connection()

    doubt = connection.execute(
        """
        SELECT user_id
        FROM doubts
        WHERE id = %s
        """,
        (doubt_id,)
    ).fetchone()

    if not doubt:
        connection.close()
        return "Doubt not found", 404

    if doubt["user_id"] != session["user_id"]:
        connection.close()
        return "You are not allowed to edit this doubt.", 403

    connection.execute(
        """
        UPDATE doubts
        SET
            title = %s,
            body = %s,
            subject = %s,
            chapter = %s,
            is_edited = TRUE
        WHERE id = %s
        """,
        (
            title,
            body,
            subject or None,
            chapter or None,
            doubt_id
        )
    )

    connection.commit()
    connection.close()

    return redirect(
        url_for(
            "view_doubt",
            doubt_id=doubt_id
        )
    )

@app.route(
    "/doubts/<int:doubt_id>/delete",
    methods=["POST"]
)
@login_required
def delete_doubt(doubt_id):

    connection = get_connection()

    doubt = connection.execute(
        """
        SELECT user_id
        FROM doubts
        WHERE id = %s
        """,
        (doubt_id,)
    ).fetchone()

    if not doubt:
        connection.close()
        return "Doubt not found", 404

    if doubt["user_id"] != session["user_id"]:
        connection.close()
        return "You are not allowed to delete this doubt.", 403

    connection.execute(
        """
        DELETE FROM doubts
        WHERE id = %s
        """,
        (doubt_id,)
    )

    connection.commit()
    connection.close()

    return redirect(
        url_for("doubts")
    )


@app.route(
    "/doubts/int:<doubt_id>/reply",
    methods=["POST"]
)
@login_required
def add_reply(doubt_id):

    body = request.form.get(
        "body",
        ""
    ).strip()

    valid, error = validate_content(body)

    if not valid:
        return redirect(
            url_for(
                "view_doubt",
                doubt_id=doubt_id,
                error=error
            )
        )

    if not body:
        return redirect(
            url_for(
                "view_doubt",
                doubt_id=doubt_id
            )
        )

    if len(body) > 3000:
        return redirect(
            url_for(
                "view_doubt",
                doubt_id=doubt_id
            )
        )

    connection = get_connection()

    reply_count = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM replies
        WHERE user_id = %s
        AND created_at >= NOW() - INTERVAL '1 hour'
        """,
        (session["user_id"],)
    ).fetchone()["count"]

    if reply_count >= MAX_REPLIES_PER_HOUR:
        connection.close()

        return redirect(
            url_for(
                "view_doubt",
                doubt_id=doubt_id,
                error=(
                    "You can post a maximum of "
                    f"{MAX_REPLIES_PER_HOUR} replies per hour."
                )
            )
        )

    doubt = connection.execute(
        """
        SELECT
            id,
            user_id,
            title
        FROM doubts
        WHERE id = %s
        """,
        (doubt_id,)
    ).fetchone()

    if not doubt:
        connection.close()

        return "Doubt not found", 404

    connection.execute(
        """
        INSERT INTO replies (
            doubt_id,
            user_id,
            body
        )
        VALUES (%s, %s, %s)
        """,
        (
            doubt_id,
            session["user_id"],
            body
        )
    )

    connection.execute(
        """
        INSERT INTO contributions (
            user_id,
            type,
            points
        )
        VALUES (%s, %s, %s)
        """,
        (
            session["user_id"],
            "doubt_reply",
            2
        )
    )

    if doubt["user_id"] != session["user_id"]:

        connection.execute(
            """
            INSERT INTO notifications (
                user_id,
                title,
                message
            )
            VALUES (%s, %s, %s)
            """,
            (
                doubt["user_id"],
                "New reply to your doubt",
                f'Someone replied to "{doubt["title"]}".'
            )
        )

    connection.commit()
    connection.close()

    return redirect(
        url_for(
            "view_doubt",
            doubt_id=doubt_id
        )
    )

@app.route(
    "/doubts/int:<doubt_id>/solution/int:<reply_id>",
    methods=["POST"]
)
@login_required
def mark_solution(
    doubt_id,
    reply_id
):

    connection = get_connection()

    doubt = connection.execute(
        """
        SELECT
            user_id,
            title
        FROM doubts
        WHERE id = %s
        """,
        (doubt_id,)
    ).fetchone()

    if not doubt:
        connection.close()

        return "Doubt not found", 404

    if doubt["user_id"] != session["user_id"]:

        connection.close()

        return (
            "Only the person who asked "
            "the doubt can mark a solution.",
            403
        )

    reply = connection.execute(
        """
        SELECT
            id,
            user_id,
            is_correct
        FROM replies
        WHERE id = %s
        AND doubt_id = %s
        """,
        (
            reply_id,
            doubt_id
        )
    ).fetchone()

    if not reply:
        connection.close()

        return "Reply not found", 404

    existing_solution = connection.execute(
        """
        SELECT id
        FROM replies
        WHERE doubt_id = %s
        AND is_correct = TRUE
        """,
        (doubt_id,)
    ).fetchone()

    if existing_solution:
        connection.close()

        return redirect(
            url_for(
                "view_doubt",
                doubt_id=doubt_id
            )
        )

    connection.execute(
        """
        UPDATE replies
        SET is_correct = TRUE
        WHERE id = %s
        """,
        (reply_id,)
    )

    connection.execute(
        """
        INSERT INTO contributions (
            user_id,
            type,
            points
        )
        VALUES (%s, %s, %s)
        """,
        (
            reply["user_id"],
            "solution",
            3
        )
    )

    if reply["user_id"] != session["user_id"]:

        connection.execute(
            """
            INSERT INTO notifications (
                user_id,
                title,
                message
            )
            VALUES (%s, %s, %s)
            """,
            (
                reply["user_id"],
                "Your reply was marked as the solution",
                f'Your answer to "{doubt["title"]}" was marked as the solution.'
            )
        )

    connection.commit()
    connection.close()

    return redirect(
        url_for(
            "view_doubt",
            doubt_id=doubt_id
        )
    )

@app.route("/profile/delete-picture", methods=["POST"])
@login_required
def delete_profile_picture():

    user_id = session["user_id"]

    connection = get_connection()

    user = connection.execute(
        """
        SELECT
            profile_picture,
            profile_picture_public_id
        FROM users
        WHERE id = %s
        """,
        (user_id,)
    ).fetchone()

    if not user:
        connection.close()
        return redirect(url_for("login"))

    public_id = user["profile_picture_public_id"]

    if public_id:

        try:

            cloudinary.uploader.destroy(
                public_id,
                resource_type="image"
            )

        except Exception:
            connection.close()
            return redirect(url_for("profile"))

    connection.execute(
        """
        UPDATE users
        SET
            profile_picture = NULL,
            profile_picture_public_id = NULL
        WHERE id = %s
        """,
        (user_id,)
    )

    connection.commit()
    connection.close()

    return redirect(url_for("profile"))

@app.route("/leaderboard")
@login_required
def leaderboard():

    connection = get_connection()

    users = connection.execute(
        """
        SELECT
            users.id,
            users.display_name,
            users.profile_picture,
            COALESCE(
                SUM(contributions.points),
                0
            ) AS points
        FROM users
        LEFT JOIN contributions
            ON users.id = contributions.user_id
        GROUP BY users.id
        ORDER BY points DESC, users.display_name ASC
        """
    ).fetchall()

    connection.close()

    return render_template(
        "leaderboard.html",
        users=users,
        current_user_id=session["user_id"]
    )

@app.route(
    "/upload",
    methods=["GET", "POST"]
)
@login_required
def upload():

    service = get_drive_service()

    subjects = get_cached_structure(
        service
    )

    if request.method == "GET":
        return render_template(
            "upload.html",
            subjects=subjects,
            error=None
        )


    subject_name = request.form.get(
        "subject",
        ""
    ).strip()

    chapter_name = request.form.get(
        "chapter",
        ""
    ).strip()


    selected_subject = next(
        (
            subject
            for subject in subjects
            if subject["name"] == subject_name
        ),
        None
    )

    if not selected_subject:

        return render_template(
            "upload.html",
            subjects=subjects,
            error="Please select a valid subject."
        )


    selected_chapter = next(
        (
            chapter
            for chapter in selected_subject["chapters"]
            if chapter["name"] == chapter_name
        ),
        None
    )

    if not selected_chapter:

        return render_template(
            "upload.html",
            subjects=subjects,
            error="Please select a valid chapter."
        )


    files = request.files.getlist(
        "files"
    )

    files = [
        file
        for file in files
        if file and file.filename
    ]


    if not files:

        return render_template(
            "upload.html",
            subjects=subjects,
            error="Please select at least one file."
        )


    connection = get_connection()


    cursor = connection.execute(
        """
        INSERT INTO upload_submissions (
            user_id,
            subject,
            chapter
        )
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (
            session["user_id"],
            subject_name,
            chapter_name
        )
    )

    submission_id = cursor.fetchone()["id"]


    submission_folder = os.path.join(
        PENDING_UPLOAD_FOLDER,
        str(submission_id)
    )

    os.makedirs(
        submission_folder,
        exist_ok=True
    )


    for file in files:

        original_filename = secure_filename(
            file.filename
        )

        if not original_filename:
            continue


        stored_filename = (
            f"{uuid.uuid4().hex}_"
            f"{original_filename}"
        )


        file.save(
            os.path.join(
                submission_folder,
                stored_filename
            )
        )


        connection.execute(
            """
            INSERT INTO upload_files (
                submission_id,
                original_filename,
                stored_filename
            )
            VALUES (%s, %s, %s)
            """,
            (
                submission_id,
                original_filename,
                stored_filename
            )
        )


    connection.commit()
    connection.close()


    return redirect(
        url_for("profile")
    )

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():

    connection = get_connection()

    submissions = connection.execute(
        """
        SELECT
            upload_submissions.id,
            upload_submissions.subject,
            upload_submissions.chapter,
            upload_submissions.status,
            upload_submissions.rejection_reason,
            upload_submissions.created_at,
            users.username,
            users.display_name
        FROM upload_submissions
        JOIN users
            ON upload_submissions.user_id = users.id
        WHERE upload_submissions.status = 'pending'
        ORDER BY upload_submissions.created_at ASC
        """
    ).fetchall()

    submission_files = {}

    for submission in submissions:

        files = connection.execute(
            """
            SELECT
                id,
                original_filename
            FROM upload_files
            WHERE submission_id = %s
            """,
            (submission["id"],)
        ).fetchall()

        submission_files[
            submission["id"]
        ] = files

    connection.close()

    return render_template(
        "admin.html",
        submissions=submissions,
        submission_files=submission_files
    )

@app.route("/admin/logout")
def admin_logout():

    session.pop(
        "is_admin",
        None
    )

    return redirect(
        url_for("admin")
    )

@app.route(
    "/admin/upload/<int:submission_id>/approve",
    methods=["POST"]
)
@admin_required
def approve_upload(submission_id):

    connection = get_connection()

    submission = connection.execute(
        """
        SELECT *
        FROM upload_submissions
        WHERE id = %s
        """,
        (submission_id,)
    ).fetchone()

    if not submission:
        connection.close()
        return "Submission not found", 404

    if submission["status"] != "pending":
        connection.close()
        return redirect(
            url_for("admin_dashboard")
        )

    files = connection.execute(
        """
        SELECT
            original_filename,
            stored_filename
        FROM upload_files
        WHERE submission_id = %s
        """,
        (submission_id,)
    ).fetchall()

    connection.close()

    service = get_drive_service()

    subjects = get_cached_structure(service)

    selected_subject = next(
        (
            subject
            for subject in subjects
            if subject["name"] == submission["subject"]
        ),
        None
    )

    if not selected_subject:
        return (
            "Subject folder not found in Google Drive.",
            500
        )

    selected_chapter = next(
        (
            chapter
            for chapter in selected_subject["chapters"]
            if chapter["name"] == submission["chapter"]
        ),
        None
    )

    if not selected_chapter:
        return (
            "Chapter folder not found in Google Drive.",
            500
        )

    submission_folder = os.path.join(
        PENDING_UPLOAD_FOLDER,
        str(submission_id)
    )

    try:

        for file in files:

            filepath = os.path.join(
                submission_folder,
                file["stored_filename"]
            )

            if not os.path.exists(filepath):
                return (
                    f"Pending file not found: "
                    f"{file['original_filename']}",
                    500
                )

            upload_file(
                service,
                filepath,
                file["original_filename"],
                selected_chapter["id"]
            )

    except Exception as error:

        print(
            f"Drive upload failed: {error}"
        )

        return (
            "The files could not be uploaded to "
            "Google Drive. The submission remains pending.",
            500
        )

    connection = get_connection()

    connection.execute(
        """
        UPDATE upload_submissions
        SET status = 'approved'
        WHERE id = %s
        """,
        (submission_id,)
    )

    connection.execute(
        """
        INSERT INTO notifications (
            user_id,
            title,
            message
        )
        VALUES (%s, %s, %s)
        """,
        (
            submission["user_id"],
            "Upload approved",
            (
                f"Your {submission['subject']} → "
                f"{submission['chapter']} upload "
                f"has been approved and added to StudySpace."
            )
        )
    )

    connection.execute(
        """
        INSERT INTO contributions (
            user_id,
            type,
            points
        )
        VALUES (%s, %s, %s)
        """,
        (
            submission["user_id"],
            "study_material_upload",
            10
        )
    )

    connection.commit()
    connection.close()

    for file in files:

        filepath = os.path.join(
            submission_folder,
            file["stored_filename"]
        )

        if os.path.exists(filepath):
            os.remove(filepath)

    try:
        os.rmdir(submission_folder)
    except OSError:
        pass

    return redirect(
        url_for("admin_dashboard")
    )

@app.route(
    "/admin/reject/<int:submission_id>",
    methods=["POST"]
)
@admin_required
def reject_upload(submission_id):

    reason = request.form.get(
        "reason",
        ""
    ).strip()

    if not reason:
        return redirect(
            url_for("admin_dashboard")
        )

    connection = get_connection()

    submission = connection.execute(
        """
        SELECT id, user_id
        FROM upload_submissions
        WHERE id = %s
        """,
        (submission_id,)
    ).fetchone()

    if not submission:
        connection.close()
        return "Submission not found", 404

    connection.execute(
        """
        UPDATE upload_submissions
        SET status = %s,
            rejection_reason = %s
        WHERE id = %s
        """,
        (
            "rejected",
            reason,
            submission_id
        )
    )

    connection.execute(
        """
        INSERT INTO notifications (
            user_id,
            title,
            message
        )
        VALUES (%s, %s, %s)
        """,
        (
            submission["user_id"],
            "Upload rejected",
            reason
        )
    )

    connection.commit()
    connection.close()

    return redirect(
        url_for("admin_dashboard")
    )

@app.route("/notifications")
@login_required
def notifications():

    connection = get_connection()

    user_notifications = connection.execute(
        """
        SELECT
            id,
            title,
            message,
            is_read,
            created_at
        FROM notifications
        WHERE user_id = %s
        ORDER BY created_at DESC
        """,
        (session["user_id"],)
    ).fetchall()

    connection.close()

    return render_template(
        "notifications.html",
        notifications=user_notifications
    )

@app.route(
    "/notifications/read/<int:notification_id>",
    methods=["POST"]
)
@login_required
def mark_notification_read(notification_id):

    connection = get_connection()

    connection.execute(
        """
        UPDATE notifications
        SET is_read = TRUE
        WHERE id = %s
        AND user_id = %s
        """,
        (
            notification_id,
            session["user_id"]
        )
    )

    connection.commit()
    connection.close()

    return redirect(
        url_for("notifications")
    )

@app.route("/notifications/read", methods=["POST"])
@login_required
def mark_notifications_read():

    connection = get_connection()

    connection.execute(
        """
        UPDATE notifications
        SET is_read = TRUE
        WHERE user_id = %s
        AND is_read = 0
        """,
        (session["user_id"],)
    )

    connection.commit()
    connection.close()

    return "", 204

@app.route("/doubts/mine")
@login_required
def my_doubts():
    connection = get_connection()

    doubts = connection.execute(
        """
        SELECT
            doubts.id,
            doubts.title,
            doubts.body,
            doubts.subject,
            doubts.chapter,
            doubts.created_at,
            users.display_name,
            users.profile_picture,
            COUNT(replies.id) AS reply_count
        FROM doubts
        JOIN users
            ON doubts.user_id = users.id
        LEFT JOIN replies
            ON doubts.id = replies.doubt_id
        WHERE doubts.user_id = %s
        GROUP BY
            doubts.id,
            doubts.title,
            doubts.body,
            doubts.subject,
            doubts.chapter,
            doubts.created_at,
            users.display_name,
            users.profile_picture
        ORDER BY doubts.created_at DESC
        """,
        (session["user_id"],)
    ).fetchall()

    connection.close()

    return render_template(
        "doubts.html",
        doubts=doubts,
        viewing_my_doubts=True
    )

@app.route(
    "/chapter/<chapter_id>"
)
@login_required
def chapter(chapter_id):

    service = get_drive_service()

    chapter = get_folder(
        service,
        chapter_id
    )

    resources = get_children(
        service,
        chapter_id
    )

    return render_template(
        "chapter.html",
        chapter=chapter,
        resources=resources
    )

@app.route(
    "/admin",
    methods=["GET", "POST"]
)
def admin():

    if session.get("is_admin"):
        return redirect(
            url_for("admin_dashboard")
        )

    if request.method == "POST":

        password = request.form.get(
            "password",
            ""
        )

        if password != os.environ["ADMIN_PASSWORD"]:
            return render_template(
                "admin_login.html",
                error="Incorrect admin password."
            )

        session["is_admin"] = True

        return redirect(
            url_for("admin_dashboard")
        )

    return render_template(
        "admin_login.html",
        error=None
    )

@app.route("/admin/upload/file/<int:file_id>")
@admin_required
def admin_view_upload(file_id):

    connection = get_connection()

    file = connection.execute(
        """
        SELECT
            upload_files.*,
            upload_submissions.user_id
        FROM upload_files
        JOIN upload_submissions
            ON upload_files.submission_id = upload_submissions.id
        WHERE upload_files.id = %s
        """,
        (file_id,)
    ).fetchone()

    connection.close()

    if not file:
        return "File not found", 404

    filepath = os.path.join(
        PENDING_UPLOAD_FOLDER,
        str(file["submission_id"]),
        file["stored_filename"]
    )

    if not os.path.exists(filepath):
        return "File no longer exists", 404

    return send_from_directory(
        os.path.dirname(filepath),
        file["stored_filename"],
        as_attachment=False
    )

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )