# Train the injury classifier. Run in Google Colab (free GPU): upload the Kaggle
# wound dataset (kaggle.com/datasets/ibrahimfateen/wound-classification), set
# DATA_DIR to its folder, Runtime > Run all. Output: model.tflite + labels.txt
import tensorflow as tf

DATA_DIR = "Wound_dataset"     # folder containing Burns/, Cut/, Bruises/, ...
IMG = 224
EPOCHS = 8

train = tf.keras.utils.image_dataset_from_directory(
    DATA_DIR, validation_split=0.2, subset="training", seed=42,
    image_size=(IMG, IMG), batch_size=32)
val = tf.keras.utils.image_dataset_from_directory(
    DATA_DIR, validation_split=0.2, subset="validation", seed=42,
    image_size=(IMG, IMG), batch_size=32)
labels = train.class_names
print("classes:", labels)

base = tf.keras.applications.MobileNetV2(input_shape=(IMG, IMG, 3),
                                         include_top=False, weights="imagenet")
base.trainable = False              # transfer learning: reuse ImageNet features

model = tf.keras.Sequential([
    tf.keras.layers.Rescaling(1.0 / 127.5, offset=-1),
    base,
    tf.keras.layers.GlobalAveragePooling2D(),
    tf.keras.layers.Dropout(0.2),
    tf.keras.layers.Dense(len(labels), activation="softmax"),
])
model.compile(optimizer="adam", loss="sparse_categorical_crossentropy",
              metrics=["accuracy"])
model.fit(train, validation_data=val, epochs=EPOCHS)

tflite = tf.lite.TFLiteConverter.from_keras_model(model).convert()
open("model.tflite", "wb").write(tflite)
open("labels.txt", "w").write("\n".join(labels))
print("wrote model.tflite + labels.txt, copy both to the Pi")
