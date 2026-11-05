//Global Variables:

var responseResult;             //Object used to store the response object
var baseURL;                    //Variable used to store base64 encoding of the image

// API logic
// When the page is opened locally it calls the Django API. On GitHub Pages (no Python server) it uses the
// same pipeline running in the browser (../../browser_backend/backend.worker.js), which returns the same JSON fields.
const LOCAL = ["localhost", "127.0.0.1", ""].includes(location.hostname);
const APIurl = `http://127.0.0.1:8000/image-process`;
let worker = null;

//Send the image to the API
const APICall = function (data, callback) {
  if (LOCAL) {
    fetch(APIurl, { method: "POST", headers: { "Content-Type": "text/plain" }, body: data })
      .then((res) => res.json())
      .then(callback)
      .catch(() => callback({ result: "Could not reach the API at " + APIurl }));
    return;
  }
  // In-browser back end: decode the image, shrink it to at most 640 px and send the pixels to the worker
  const img = new Image();
  img.onload = () => {
    const scale = Math.min(1, 640 / Math.max(img.naturalWidth, img.naturalHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(img.naturalWidth * scale);
    canvas.height = Math.round(img.naturalHeight * scale);
    const ctx = canvas.getContext("2d");
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    const rgba = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    if (!worker) worker = new Worker("../../browser_backend/backend.worker.js");
    worker.onmessage = (e) => callback(e.data.ok ? e.data.result : { result: e.data.error });
    worker.postMessage({ id: 1, width: canvas.width, height: canvas.height, rgba });
  };
  img.src = "data:image/jpeg;base64," + data;
};

//Necessary image variables
let file = new Image();
const validExtensions = ["image/jpeg", "image/png"];

//Data Module
function clearGarbage() {
  responseResult = undefined;
  file = undefined;
};

//UI Module : #00aa55

//Block of code to set the file reading process: parse loaded image into base64 encoding and send that data to API
let fileReader = new FileReader();
fileReader.onload = () => showAndSend(fileReader.result);

//Show the image on the page and send it to the API (used by file upload and the camera)
function showAndSend(fileURL) {
  //Get the base64 Data from the image
  baseURL = fileURL.split(",")[1];
  
  //Sending it to the API
  APICall(baseURL, setResult);     //Adding callback function to the APICall method
  
  //loading the image on the page
  let imgTag = `<img src="${fileURL}" alt="" id="uploadImage" >`;
  imgHolder.innerHTML = imgTag;
  document.querySelector("#resultContainer").scrollIntoView({ behavior: "smooth" });
}

//setResult:  This function will take values from the response and necessary elements will be altered.
const setResult = function (data) {
  const result = document.querySelector("#result");
  const colorSwatch = document.querySelector(".result-color");
  
  result.textContent = data.result;
  colorSwatch.style.backgroundColor = data.colorR == null ? "transparent"
    : `rgb(${Math.trunc(data.colorR)},${Math.trunc(data.colorG)},${Math.trunc(data.colorB)})`;
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

upButton.onclick = () => input.click();
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

/* Take Photo: open the camera, capture a frame and analyse it like an uploaded file */
const cameraBtn = document.querySelector(".btn-camera");
const cameraBox = document.querySelector(".camera");
const video = cameraBox.querySelector("video");
const dragPrompt = [dragText, dragArea.querySelector("p"), upButton, cameraBtn];
let stream = null;

function closeCamera() {
  if (stream) stream.getTracks().forEach((t) => t.stop());
  stream = null;
  cameraBox.hidden = true;
  dragPrompt.forEach((el) => (el.hidden = false));
}

cameraBtn.addEventListener("click", async () => {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    dragText.textContent = "This browser can't open the camera. Use Browse File instead.";
    return;
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
    video.srcObject = stream;
    await video.play();
    dragPrompt.forEach((el) => (el.hidden = true));
    cameraBox.hidden = false;
  } catch (err) {
    dragText.textContent = "Camera not available: allow camera access or use Browse File.";
    closeCamera();
  }
});

document.querySelector("#captureBtn").addEventListener("click", () => {
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  closeCamera();
  clearGarbage();
  showAndSend(canvas.toDataURL("image/jpeg", 0.92));
});

document.querySelector("#cancelCamera").addEventListener("click", closeCamera);
