document.querySelectorAll(".like-button").forEach((likeButton) => {
  likeButton.addEventListener("click", function () {
    const recipeId = this.getAttribute("data-recipe-id");

    fetch(`/like/${recipeId}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": document
          .querySelector('meta[name="csrf-token"]')
          .getAttribute("content"),
      },
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.status === "liked") {
          this.textContent = "🧡";
        } else if (data.status === "unliked") {
          this.textContent = "💛";
        }
        document.getElementById(`likes-count-${recipeId}`).textContent =
          data.likes_count;
      })
      .catch((error) => console.error("Error:", error));
  });
});



const slider = document.getElementById("numServings");
const output = document.getElementById("rangeValue");
output.innerHTML = slider.value; // Display the default value

slider.oninput = function () {
  output.innerHTML = this.value;
};