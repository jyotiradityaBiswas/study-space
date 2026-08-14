const root = document.documentElement;
const toggle = document.getElementById("theme-toggle");
const icon = document.getElementById("theme-icon");

const savedTheme = localStorage.getItem("theme");

const removePictureButton =
    document.getElementById("open-remove-picture");

const deleteAccountButton =
    document.getElementById("open-delete-account");

const removePictureModal =
    document.getElementById("remove-picture-modal");

const deleteAccountModal =
    document.getElementById("delete-account-modal");

const notificationButton =
    document.getElementById("notification-button");

const notificationPopup =
    document.getElementById("notification-popup");


if (savedTheme) {
    root.dataset.theme = savedTheme;
}


function updateIcon() {
    if (!icon) {
        return;
    }

    icon.textContent =
        root.dataset.theme === "dark"
            ? "☀"
            : "☾";
}


updateIcon();


if (toggle) {
    toggle.addEventListener(
        "click",
        () => {

            const currentTheme =
                root.dataset.theme || "light";

            const newTheme =
                currentTheme === "dark"
                    ? "light"
                    : "dark";

            root.dataset.theme = newTheme;

            localStorage.setItem(
                "theme",
                newTheme
            );

            updateIcon();
        }
    );
}


function openModal(modal) {

    if (!modal) {
        return;
    }

    modal.hidden = false;

    document.body.classList.add(
        "modal-open"
    );
}


function closeModal(modal) {

    if (!modal) {
        return;
    }

    modal.hidden = true;

    if (
        (!removePictureModal ||
            removePictureModal.hidden) &&
        (!deleteAccountModal ||
            deleteAccountModal.hidden)
    ) {
        document.body.classList.remove(
            "modal-open"
        );
    }
}


if (removePictureButton) {

    removePictureButton.addEventListener(
        "click",
        () => {
            openModal(
                removePictureModal
            );
        }
    );
}


if (deleteAccountButton) {

    deleteAccountButton.addEventListener(
        "click",
        () => {

            openModal(
                deleteAccountModal
            );

            const passwordInput =
                document.getElementById(
                    "delete-password"
                );

            if (passwordInput) {

                setTimeout(
                    () => {
                        passwordInput.focus();
                    },
                    50
                );

            }
        }
    );
}


document
    .querySelectorAll("[data-close-modal]")
    .forEach((button) => {

        button.addEventListener(
            "click",
            () => {

                closeModal(
                    button.closest(
                        ".modal-overlay"
                    )
                );

            }
        );

    });


document
    .querySelectorAll(".modal-overlay")
    .forEach((overlay) => {

        overlay.addEventListener(
            "click",
            (event) => {

                if (
                    event.target === overlay
                ) {
                    closeModal(overlay);
                }

            }
        );

    });


document.addEventListener(
    "keydown",
    (event) => {

        if (event.key !== "Escape") {
            return;
        }

        closeModal(
            removePictureModal
        );

        closeModal(
            deleteAccountModal
        );

    }
);


if (
    notificationButton &&
    notificationPopup
) {

    notificationButton.addEventListener(
        "click",
        async (event) => {

            event.stopPropagation();

            notificationPopup.hidden =
                !notificationPopup.hidden;


            if (!notificationPopup.hidden) {

                try {

                    const response =
                        await fetch(
                            "/notifications/read",
                            {
                                method: "POST"
                            }
                        );


                    if (!response.ok) {
                        throw new Error(
                            "Failed to mark notifications as read."
                        );
                    }


                    const badge =
                        document.querySelector(
                            ".notification-badge"
                        );


                    if (badge) {
                        badge.remove();
                    }


                    document
                        .querySelectorAll(
                            ".notification-popup-item.unread"
                        )
                        .forEach((item) => {

                            item.classList.remove(
                                "unread"
                            );

                        });


                    document
                        .querySelectorAll(
                            ".notification-popup-dot"
                        )
                        .forEach((dot) => {

                            dot.remove();

                        });


                } catch (error) {

                    console.error(
                        "Failed to mark notifications as read:",
                        error
                    );

                }

            }

        }
    );


    document.addEventListener(
        "click",
        (event) => {

            if (
                !notificationPopup.contains(
                    event.target
                ) &&
                !notificationButton.contains(
                    event.target
                )
            ) {

                notificationPopup.hidden =
                    true;

            }

        }
    );

}

document
    .querySelectorAll("form")
    .forEach((form) => {

        const approvalButton =
            form.querySelector(
                "#approval-button"
            );

        if (!approvalButton) {
            return;
        }

        form.addEventListener(
            "submit",
            () => {

                if (approvalButton.disabled) {
                    return;
                }

                approvalButton.disabled = true;

                approvalButton.textContent =
                    "Submitting...";

            }
        );

    });
    
document
    .querySelectorAll(".password-toggle")
    .forEach((button) => {

        button.addEventListener(
            "click",
            () => {

                const inputId =
                    button.getAttribute(
                        "aria-controls"
                    );

                const input =
                    document.getElementById(
                        inputId
                    );

                const icon =
                    button.querySelector("img");

                if (!input || !icon) {
                    return;
                }

                const isPassword =
                    input.type === "password";

                input.type =
                    isPassword
                        ? "text"
                        : "password";

                icon.src =
                    isPassword
                        ? "/static/images/eye-off.svg"
                        : "/static/images/eye.svg";

                button.setAttribute(
                    "aria-label",
                    isPassword
                        ? "Hide password"
                        : "Show password"
                );
            }
        );

    });