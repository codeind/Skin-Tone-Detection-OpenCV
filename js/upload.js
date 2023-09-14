//Global Variables:

var responseResult;             //Object used to store the response object
var baseURL;                    //Variable used to store base64 encoding of the image

// API logic
const APIurl = `http://127.0.0.1:8000/image-process`;

//Send the image to the API
const APICall = function (data, callback) {
  var result;
 
  const xhr = new XMLHttpRequest();
  xhr.onload = () => {
    if (xhr.status >= 200 && xhr.status < 300) {
      result = JSON.parse(xhr.response);
    }
  };
  xhr.open("POST", APIurl, false);
  xhr.setRequestHeader("Content-Type", "text/plain");
  xhr.send(data);

  callback(result);
};

//Necessary image variables
let file = new Image();
const validExtensions = ["image/jpeg"];

//Data Module
function clearGarbage() {
  responseResult = undefined;
  file = undefined;
};

//UI Module : #00aa55

//Block of code to set the file reading process: parse loaded image into base64 encoding and send that data to API
let fileReader = new FileReader();
fileReader.onload = () => {
  //Get the base64 Data from the image
  let fileURL = fileReader.result;
  baseURL = fileURL.split(",")[1];
  
  //Sending it to the API
  responseResult = APICall(baseURL, setResult);     //Adding callback function to the APICall method
  
  //loading the image on the page
  let imgTag = `<img src="${fileURL}" alt="" id="uploadImage" >`;
  imgHolder.innerHTML = imgTag;
};

//setResult:  This function will take values from the response and necessary elements will be altered.
const setResult = function (data) {
  const result = document.querySelector("#result");
  const colorSwatch = document.querySelector(".result-color");
  
  result.textContent = data.result;
  colorSwatch.style.backgroundColor = `rgb(${Math.trunc(data.colorR)},${Math.trunc(data.colorG)},${Math.trunc(data.colorB)})`;
};



//Selecting necessary elements
const dragArea = document.querySelector(".drag-area");
const dragText = document.querySelector(".header");
const upButton = document.querySelector(".btn-upload");
const input = document.querySelector("input");
const imgHolder = document.querySelector(".img-holder");


/* #fed223 EVENTS */

// Event 1: Image is dragged on the container
dragArea.addEventListener("dragover", (e) => {
  e.preventDefault();
  dragArea.classList.add("active");
  dragText.textContent = "Release File to Upload";
});


// Event 2: Image is leaving container 
dragArea.addEventListener("dragleave", () => {
  dragArea.classList.remove("active");
  dragText.textContent = "Drag and drop file to upload";
});


// Event 3: Image is dropped on the container
dragArea.addEventListener("drop", (e) => {
  e.preventDefault();
  
  clearGarbage();
  file = e.dataTransfer.files[0];
  if (file) {
    if (validExtensions.includes(file.type)) {
      try {
        fileReader.readAsDataURL(file);
      } catch (err) {
      }
      dragArea.classList.remove("active");
      dragText.textContent = "Drag and drop file to upload";
    }
  }
});
//Upload button functionality

upButton.onclick = () => {
  input.click();
  input.addEventListener("change", function () {
    clearGarbage();
    file = this.files[0];
    
    if (file) {
      if (validExtensions.includes(file.type)) {
        try {
          fileReader.readAsDataURL(file);
        } catch (err) {
        }
      }
    }
  });
};