class LayoutFactory:
    @classmethod
    def create(cls, name: str):
        from src.layouts.image_below import ImageBelowLayout
        from src.layouts.image_full import ImageFullLayout
        from src.layouts.image_right import ImageRightLayout
        from src.layouts.text_only import TextOnlyLayout

        layouts = {
            "text-only": TextOnlyLayout,
            "image-right": ImageRightLayout,
            "image-below": ImageBelowLayout,
            "image-full": ImageFullLayout,
        }
        return layouts.get(name, TextOnlyLayout)()
