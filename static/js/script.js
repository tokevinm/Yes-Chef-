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



// Get slider and output elements
const slider = document.getElementById("numServings");
const output = document.getElementById("rangeValue");
const ingredientsList = document.getElementById("ingredientsList");

// Display the default slider value
output.innerHTML = slider.value;

// Base servings from the initial value (e.g., original recipe servings)
const baseServings = parseInt(slider.value, 10);

// Update ingredients when the slider is changed
slider.oninput = function() {
  const newServings = parseInt(this.value, 10);
  output.innerHTML = newServings;

  // Loop through each ingredient in the list
  ingredientsList.querySelectorAll("li").forEach((ingredientElement) => {
    const baseAmount = parseFloat(ingredientElement.getAttribute("data-amount"));
    
    // Recalculate the new amount based on the ratio of new servings to base servings
    const newAmount = (baseAmount / baseServings) * newServings;

    // Update the displayed amount in the ingredient list
    ingredientElement.querySelector(".amount").innerHTML = newAmount.toFixed(2); // Adjust precision as needed
  });
};

// const slider = document.getElementById("numServings");
// const output = document.getElementById("rangeValue");
// output.innerHTML = slider.value; // Display the default value

// slider.oninput = function () {
//   output.innerHTML = this.value;
// };