function likeStory(storyId) {

    fetch(`/api/like?id=${storyId}`)
        .then(response => response.json())
        .then(data => {
            if (data.status === "success") {
                // Optionally, update UI
            }
        });
}

function dislikeStory(storyId) {

    fetch(`/api/dislike?id=${storyId}`)
        .then(response => response.json())
        .then(data => {
            if (data.status === "success") {
                event.target.closest('.list-group-item').remove();
            }
        });
}

function selectTag(tagId) {
    fetch(`/api/tagselect?id=${tagId}`)
        .then(response => response.json())
        .then(data => {
            if (data.status === "success") {
                let tagElement = document.querySelector(`#available-tags li:contains('${tagId}')`);
                tagElement.remove();
                document.getElementById('chosen-tags').appendChild(tagElement);
            }
        });
}

function deselectTag(tagId) {
    fetch(`/api/tagdeselect?id=${tagId}`)
        .then(response => response.json())
        .then(data => {
            if (data.status === "success") {
                let tagElement = document.querySelector(`#chosen-tags li:contains('${tagId}')`);
                tagElement.remove();
                document.getElementById('available-tags').appendChild(tagElement);
            }
        });
}
