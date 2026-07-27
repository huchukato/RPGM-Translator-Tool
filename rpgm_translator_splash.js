var Imported = Imported || {};
Imported.RPGMTranslatorSplash = true;

(function() {
    "use strict";

    var parameters = PluginManager.parameters("rpgm_translator_splash");
    var pictureName = String(parameters["Picture"] || "splash");
    var duration = Number(parameters["Duration"] || 180);
    var shown = false;
    var originalGoto = SceneManager.goto;

    function Scene_RPGMTranslatorSplash() {
        this.initialize.apply(this, arguments);
    }

    Scene_RPGMTranslatorSplash.prototype = Object.create(Scene_Base.prototype);
    Scene_RPGMTranslatorSplash.prototype.constructor = Scene_RPGMTranslatorSplash;

    Scene_RPGMTranslatorSplash.prototype.initialize = function() {
        Scene_Base.prototype.initialize.call(this);
        this._frames = 0;
        this._skipRequested = false;
        this._skipHandler = function() {
            this._skipRequested = true;
        }.bind(this);
        document.addEventListener("keydown", this._skipHandler);
    };

    Scene_RPGMTranslatorSplash.prototype.terminate = function() {
        document.removeEventListener("keydown", this._skipHandler);
        Scene_Base.prototype.terminate.call(this);
    };

    Scene_RPGMTranslatorSplash.prototype.create = function() {
        Scene_Base.prototype.create.call(this);
        this._background = new Sprite(new Bitmap(Graphics.width, Graphics.height));
        this._background.bitmap.fillAll("#000000");
        this.addChild(this._background);
        this._picture = new Sprite(ImageManager.loadPicture(pictureName));
        this._picture.opacity = 0;
        this.addChild(this._picture);
    };

    Scene_RPGMTranslatorSplash.prototype.update = function() {
        Scene_Base.prototype.update.call(this);
        this._frames += 1;
        if (this._picture.bitmap.isReady()) {
            this._fitPicture();
        }
        if (this._frames >= duration || this._skipRequested || TouchInput.isTriggered()) {
            SceneManager.goto(Scene_Title);
        }
    };

    Scene_RPGMTranslatorSplash.prototype._fitPicture = function() {
        var width = this._picture.bitmap.width;
        var height = this._picture.bitmap.height;
        if (!width || !height) {
            return;
        }
        var scale = Math.min(Graphics.width / width, Graphics.height / height);
        this._picture.scale.x = scale;
        this._picture.scale.y = scale;
        this._picture.x = (Graphics.width - width * scale) / 2;
        this._picture.y = (Graphics.height - height * scale) / 2;
        this._picture.opacity = 255;
    };

    SceneManager.goto = function(sceneClass) {
        if (!shown && sceneClass === Scene_Title) {
            shown = true;
            return originalGoto.call(this, Scene_RPGMTranslatorSplash);
        }
        return originalGoto.apply(this, arguments);
    };
})();
